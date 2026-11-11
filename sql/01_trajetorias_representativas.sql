-- Abordagem TR: trajetorias representativas, adaptada de Oliveira & Barbosa.
-- Entrada: public.p2_regiao_movel (id_incendio bigint, data date,
--                                 rank_global integer, geom geometry 4326).
-- Multiplos IDs sao mantidos isolados por PARTITION BY / GROUP BY.
-- Requer PostGIS 3+; geometrias poligonais VALIDAS, WGS84, uma linha por ID/data.

CREATE SCHEMA IF NOT EXISTS analise;

CREATE OR REPLACE VIEW analise.tr_pontos AS
WITH base AS (
    SELECT id_incendio, data, rank_global, geom,
           ST_Centroid(geom::geography)::geometry AS centroide
    FROM public.p2_regiao_movel
),
extremos AS (
    SELECT b.id_incendio, b.data, b.rank_global,
           t.tipo AS descritor, v.geom AS ponto,
           ROW_NUMBER() OVER (
             PARTITION BY b.id_incendio, b.data, t.tipo
             ORDER BY
               CASE t.tipo
                 WHEN 'norte' THEN -ST_Y(v.geom)
                 WHEN 'sul' THEN ST_Y(v.geom)
                 WHEN 'leste' THEN -ST_X(v.geom)
                 WHEN 'oeste' THEN ST_X(v.geom)
               END ASC,
               CASE WHEN t.tipo IN ('norte', 'sul')
                 THEN ABS(ST_X(v.geom) - ST_X(b.centroide))
                 ELSE ABS(ST_Y(v.geom) - ST_Y(b.centroide)) END ASC,
               ST_X(v.geom), ST_Y(v.geom)
           ) AS posicao
    FROM base b
    CROSS JOIN LATERAL ST_Dump(b.geom) AS p
    CROSS JOIN LATERAL ST_DumpPoints(ST_ExteriorRing(p.geom)) AS v
    CROSS JOIN (VALUES ('norte'), ('sul'), ('leste'), ('oeste')) AS t(tipo)
)
SELECT id_incendio, data, rank_global, 'centroide'::text AS descritor,
       centroide AS ponto
FROM base
UNION ALL
SELECT id_incendio, data, rank_global, descritor, ponto
FROM extremos
WHERE posicao = 1;

CREATE OR REPLACE VIEW analise.tr_segmentos AS
WITH sequencia AS (
    SELECT id_incendio, descritor, data AS data_atual, ponto AS ponto_atual,
           LAG(data) OVER janela AS data_anterior,
           LAG(ponto) OVER janela AS ponto_anterior
    FROM analise.tr_pontos
    WINDOW janela AS (PARTITION BY id_incendio, descritor ORDER BY data)
),
medidas AS (
    SELECT *, (data_atual - data_anterior) AS dias_intervalo,
           ST_Distance(ponto_anterior::geography, ponto_atual::geography) AS distancia_m,
           ST_Azimuth(ponto_anterior::geography, ponto_atual::geography) AS azimute_rad
    FROM sequencia
    WHERE ponto_anterior IS NOT NULL
)
SELECT id_incendio, descritor, data_anterior, data_atual, dias_intervalo,
       distancia_m / 1000.0 AS distancia_geodesica_km,
       DEGREES(azimute_rad) AS azimute_geodesico_graus,
       CASE descritor
         WHEN 'norte' THEN COALESCE(distancia_m * COS(azimute_rad), 0) / 1000.0
         WHEN 'sul' THEN COALESCE(-distancia_m * COS(azimute_rad), 0) / 1000.0
         WHEN 'leste' THEN COALESCE(distancia_m * SIN(azimute_rad), 0) / 1000.0
         WHEN 'oeste' THEN COALESCE(-distancia_m * SIN(azimute_rad), 0) / 1000.0
       END AS delta_eixo_orientado_km,
       (distancia_m / 1000.0) / NULLIF(dias_intervalo, 0) AS distancia_media_km_dia
FROM medidas;

CREATE OR REPLACE VIEW analise.tr_linhas AS
SELECT id_incendio, descritor, MIN(data) AS inicio, MAX(data) AS fim,
       COUNT(*) AS observacoes, ST_MakeLine(ponto ORDER BY data) AS geom
FROM analise.tr_pontos
GROUP BY id_incendio, descritor
HAVING COUNT(*) >= 2;
