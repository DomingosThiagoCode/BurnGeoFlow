-- Visao comparativa TR x IGT: transicoes identificadas por evento e datas.
-- Um azimute de deslocamento do centroide (TR) nao equivale ao azimute da
-- distribuicao espacial das novas areas (IGT): compare como descritores.

CREATE OR REPLACE VIEW analise.tr_igt_comparacao AS
SELECT i.id_incendio, i.data_anterior, i.data_atual, i.dias_intervalo,
       i.area_nova_km2, i.area_perdida_km2, i.incremento_liquido_km2,
       i.numero_componentes_incremento, i.maior_componente_incremento_km2,
       i.fracao_maior_componente, i.azimute_medio_ponderado_graus,
       i.concentracao_direcional,
       c.distancia_geodesica_km AS deslocamento_centroide_tr_km,
       c.azimute_geodesico_graus AS azimute_centroide_tr_graus,
       n.delta_eixo_orientado_km AS avanco_norte_tr_km,
       s.delta_eixo_orientado_km AS avanco_sul_tr_km,
       l.delta_eixo_orientado_km AS avanco_leste_tr_km,
       o.delta_eixo_orientado_km AS avanco_oeste_tr_km
FROM analise.igt_indicadores i
JOIN analise.tr_segmentos c ON c.id_incendio = i.id_incendio
  AND c.data_anterior = i.data_anterior AND c.data_atual = i.data_atual
  AND c.descritor = 'centroide'
JOIN analise.tr_segmentos n ON n.id_incendio = i.id_incendio
  AND n.data_anterior = i.data_anterior AND n.data_atual = i.data_atual
  AND n.descritor = 'norte'
JOIN analise.tr_segmentos s ON s.id_incendio = i.id_incendio
  AND s.data_anterior = i.data_anterior AND s.data_atual = i.data_atual
  AND s.descritor = 'sul'
JOIN analise.tr_segmentos l ON l.id_incendio = i.id_incendio
  AND l.data_anterior = i.data_anterior AND l.data_atual = i.data_atual
  AND l.descritor = 'leste'
JOIN analise.tr_segmentos o ON o.id_incendio = i.id_incendio
  AND o.data_anterior = i.data_anterior AND o.data_atual = i.data_atual
  AND o.descritor = 'oeste';
