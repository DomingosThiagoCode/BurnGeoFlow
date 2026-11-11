-- Abordagem IGT: incrementos geometricos temporais da area acumulada P2.
-- Esta implementacao segue R(t_atual) \ R(t_anterior), conforme organograma
-- fornecido pelo projeto. A equivalencia ao artigo do INPE ainda requer leitura.
-- Executar apos 01_trajetorias_representativas.sql (mesma entrada e schema).

CREATE OR REPLACE VIEW analise.igt_geometrias AS
WITH pares AS (
    SELECT id_incendio, data AS data_atual, geom AS regiao_atual,
           LAG(data) OVER janela AS data_anterior,
           LAG(geom) OVER janela AS regiao_anterior
    FROM public.p2_regiao_movel
    WINDOW janela AS (PARTITION BY id_incendio ORDER BY data)
)
SELECT id_incendio, data_anterior, data_atual,
       data_atual - data_anterior AS dias_intervalo,
       regiao_anterior, regiao_atual,
       ST_CollectionExtract(ST_Difference(regiao_atual, regiao_anterior), 3) AS geom_incremento,
       ST_CollectionExtract(ST_Difference(regiao_anterior, regiao_atual), 3) AS geom_perda
FROM pares
WHERE regiao_anterior IS NOT NULL;

CREATE OR REPLACE VIEW analise.igt_componentes AS
WITH partes AS (
    SELECT g.id_incendio, g.data_anterior, g.data_atual,
           g.dias_intervalo, g.regiao_anterior,
           p.geom AS geom_componente
    FROM analise.igt_geometrias g
    CROSS JOIN LATERAL ST_Dump(g.geom_incremento) AS p
),
medidas AS (
    SELECT *, ST_Area(geom_componente::geography) / 1e6 AS area_km2,
           ST_Centroid(geom_componente::geography)::geometry AS centroide_incremento,
           ST_Centroid(regiao_anterior::geography)::geometry AS centroide_anterior
    FROM partes
)
SELECT id_incendio, data_anterior, data_atual, dias_intervalo,
       ROW_NUMBER() OVER (
           PARTITION BY id_incendio, data_anterior, data_atual
           ORDER BY area_km2 DESC, ST_X(centroide_incremento), ST_Y(centroide_incremento)
       ) AS componente_rank,
       area_km2, centroide_incremento,
       DEGREES(ST_Azimuth(centroide_anterior::geography,
                          centroide_incremento::geography)) AS azimute_incremento_graus,
       geom_componente AS geom
FROM medidas
WHERE area_km2 > 0;

CREATE OR REPLACE VIEW analise.igt_indicadores AS
WITH vetores AS (
    SELECT id_incendio, data_anterior, data_atual, COUNT(*) AS numero_componentes,
           SUM(area_km2) AS soma_areas_componentes_km2,
           MAX(area_km2) AS maior_componente_km2,
           SUM(area_km2 * SIN(RADIANS(azimute_incremento_graus))) AS vetor_leste,
           SUM(area_km2 * COS(RADIANS(azimute_incremento_graus))) AS vetor_norte
    FROM analise.igt_componentes
    GROUP BY id_incendio, data_anterior, data_atual
)
SELECT g.id_incendio, g.data_anterior, g.data_atual, g.dias_intervalo,
       ST_Area(g.regiao_anterior::geography) / 1e6 AS area_anterior_km2,
       ST_Area(g.regiao_atual::geography) / 1e6 AS area_atual_km2,
       ST_Area(g.geom_incremento::geography) / 1e6 AS area_nova_km2,
       ST_Area(g.geom_perda::geography) / 1e6 AS area_perdida_km2,
       (ST_Area(g.regiao_atual::geography) - ST_Area(g.regiao_anterior::geography)) / 1e6
         AS incremento_liquido_km2,
       COALESCE(v.numero_componentes, 0) AS numero_componentes_incremento,
       COALESCE(v.maior_componente_km2, 0) AS maior_componente_incremento_km2,
       CASE WHEN ST_Area(g.geom_incremento::geography) > 0
           THEN COALESCE(v.maior_componente_km2, 0) /
                (ST_Area(g.geom_incremento::geography) / 1e6) END
           AS fracao_maior_componente,
       -- 1% de coerencia vetorial minima; menor que isso: direcao indefinida.
       CASE WHEN v.soma_areas_componentes_km2 > 0 AND
           SQRT(POWER(v.vetor_leste, 2) + POWER(v.vetor_norte, 2)) /
           v.soma_areas_componentes_km2 >= 0.01
           THEN CASE WHEN DEGREES(ATAN2(v.vetor_leste, v.vetor_norte)) < 0
               THEN DEGREES(ATAN2(v.vetor_leste, v.vetor_norte)) + 360
               ELSE DEGREES(ATAN2(v.vetor_leste, v.vetor_norte)) END
       END AS azimute_medio_ponderado_graus,
       CASE WHEN v.soma_areas_componentes_km2 > 0
           THEN SQRT(POWER(v.vetor_leste, 2) + POWER(v.vetor_norte, 2)) /
                v.soma_areas_componentes_km2 END AS concentracao_direcional,
       g.geom_incremento AS geom
FROM analise.igt_geometrias g
LEFT JOIN vetores v USING (id_incendio, data_anterior, data_atual);
