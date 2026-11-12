#!/usr/bin/env python3
"""Etapa 4: diagnostico independente das trajetorias de P2.

Implementa trajetorias representativas (TR) de Oliveira & Barbosa (2025),
reexecuta a regra de rastreamento GEE e acrescenta diagnosticos geometricos
do poligono integral. Incrementos geometricos temporais (IGT) sao calculados
em modulo separado, sem afirmar equivalencia a fonte bibliografica externa.

P2 representa area queimada ACUMULADA e nao a frente ativa do incendio.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
from hashlib import sha256
import json
from math import isclose, isfinite
from pathlib import Path
import sys

import pyproj
import shapely
from shapely.geometry import Point, LineString, shape, mapping

from burngeoflow.analises.paisagem import (
    Patch, carregar_p1, indice_forma_vetorial, projetar_patches, salvar_csv,
)
from burngeoflow.validacao.topologia_p2 import reconciliar_p2

PONTOS = ("centroide", "norte", "sul", "leste", "oeste")
CAMPOS_PONTOS = ["id_incendio", "data", "rank_p2", "ponto", "longitude",
                 "latitude", "x_laea_m", "y_laea_m", "empates_extremo"]
CAMPOS_FEIXES = ["id_incendio", "data_anterior", "data_atual",
                 "dias_intervalo", "ponto", "distancia_geodesica_km",
                 "azimute_geodesico_graus", "delta_x_laea_km", "delta_y_laea_km",
                 "delta_eixo_orientado_km", "distancia_media_km_dia"]
CAMPOS_REGIAO = [
    "id_incendio", "data_anterior", "data_atual", "dias_intervalo",
    "rank_anterior", "rank_atual", "area_anterior_km2", "area_atual_km2",
    "area_nova_p2_km2", "area_perdida_p2_km2", "incremento_liquido_km2",
    "retencao_area_anterior_pct", "jaccard_geometrico",
    "perimetro_anterior_km", "perimetro_atual_km",
    "indice_forma_anterior", "indice_forma_atual", "delta_indice_forma",
    "deslocamento_centroide_km", "azimute_centroide_graus",
    "avanco_norte_km", "avanco_sul_km", "avanco_leste_km",
    "avanco_oeste_km", "delta_amplitude_ns_km", "delta_amplitude_lo_km",
    "numero_componentes_p1_anterior", "numero_componentes_p1_atual",
    "lacuna_temporal",
]
CAMPOS_RASTREAMENTO = [
    "id_incendio", "data", "dias_intervalo", "rank_p2_exportado",
    "rank_reproduzido", "confere", "criterio_reproduzido",
    "area_intersecao_maxima_km2", "distancia_minima_fallback_km",
    "empate_melhor_escore", "numero_componentes_p1",
]


def vertices_exteriores(geom):
    """Vértices do contorno exterior original, incluindo multipartes."""
    if geom.is_empty or geom.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError("A regiao deve ser poligonal e nao vazia")
    partes = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    vertices = [tuple(xy[:2]) for p in partes for xy in p.exterior.coords[:-1]]
    if not vertices:
        raise ValueError("Regiao sem vertices exteriores")
    return vertices


def pontos_cardeais(geo_original, geom_laea, transformador, inverso):
    """Extrai extremos da base WGS84 e centroide de area em LAEA.

    Empates na latitude/longitude extrema sao resolvidos por proximidade
    ortogonal ao centroide, depois pela coordenada secundaria. Esta regra
    deixa o ponto escolhido deterministico, diferentemente do SQL original
    com FIRST_VALUE sem segundo criterio de ordenacao.
    """
    vertices = vertices_exteriores(geo_original)
    centro = geom_laea.centroid
    lon_c, lat_c = inverso.transform(centro.x, centro.y)
    valores = {"norte": (1, True), "sul": (1, False),
               "leste": (0, True), "oeste": (0, False)}
    saida = {"centroide": ((lon_c, lat_c), (centro.x, centro.y), 1)}
    for nome, (indice, maximo) in valores.items():
        extremo = (max if maximo else min)(p[indice] for p in vertices)
        empatados = [p for p in vertices if abs(p[indice] - extremo) <= 1e-12]
        ortogonal = 1 - indice
        referencia = lat_c if ortogonal == 1 else lon_c
        escolhido = min(empatados, key=lambda p:
                       (abs(p[ortogonal] - referencia), p[ortogonal], p))
        saida[nome] = (escolhido, transformador.transform(*escolhido),
                       len(set(empatados)))
    return saida


def distancia_direcao(geod: pyproj.Geod, a, b):
    lon1, lat1 = a
    lon2, lat2 = b
    azimute, _, distancia = geod.inv(lon1, lat1, lon2, lat2)
    if not (isfinite(distancia) and distancia >= 0):
        raise ValueError("Distancia geodesica invalida")
    return distancia / 1000, (azimute % 360 if distancia > 1e-6 else None)


def indicadores_poligono(anterior: Patch, atual: Patch, dias: int) -> dict:
    if dias <= 0:
        raise ValueError("Transicao precisa ter intervalo positivo")
    g0, g1 = anterior.geometria, atual.geometria
    if not (g0.is_valid and g1.is_valid and g0.area > 0 and g1.area > 0):
        raise ValueError("Geometrias devem ser validas, metricas e nao vazias")
    area_inter = g0.intersection(g1).area
    area_uniao = g0.union(g1).area
    if area_inter > min(g0.area, g1.area) + 1e-5:
        raise ValueError("Intersecao impossivel")
    minx0, miny0, maxx0, maxy0 = g0.bounds
    minx1, miny1, maxx1, maxy1 = g1.bounds
    n, s = (maxy1-maxy0)/1000, (miny0-miny1)/1000
    e, w = (maxx1-maxx0)/1000, (minx0-minx1)/1000
    area0, area1 = g0.area/1e6, g1.area/1e6
    return {
        "area_anterior_km2": area0, "area_atual_km2": area1,
        "area_nova_p2_km2": max(0., (g1.area-area_inter)/1e6),
        "area_perdida_p2_km2": max(0., (g0.area-area_inter)/1e6),
        "incremento_liquido_km2": area1-area0,
        "retencao_area_anterior_pct": 100*area_inter/g0.area,
        "jaccard_geometrico": area_inter/area_uniao,
        "perimetro_anterior_km": g0.length/1000,
        "perimetro_atual_km": g1.length/1000,
        "indice_forma_anterior": indice_forma_vetorial(g0.area, g0.length),
        "indice_forma_atual": indice_forma_vetorial(g1.area, g1.length),
        "delta_indice_forma": (indice_forma_vetorial(g1.area, g1.length)
                              - indice_forma_vetorial(g0.area, g0.length)),
        "avanco_norte_km": n, "avanco_sul_km": s,
        "avanco_leste_km": e, "avanco_oeste_km": w,
        "delta_amplitude_ns_km": n+s, "delta_amplitude_lo_km": e+w,
        "lacuna_temporal": dias > 1,
    }


def reproduzir_rastreamento(por_data: dict[str, list[Patch]],
                           ranks_p2: dict[str, int]):
    """Reexecuta: primeiro maior; depois maior intersecao; fallback distancia.

    Empates nao sao determinados por sort no GEE. Nesta reproducao sao
    desempatados por rank e identificados para auditoria.
    """
    if set(por_data) != set(ranks_p2):
        raise ValueError("Datas de P1 e P2 precisam coincidir")
    linhas = []
    escolhido = None
    data_anterior = None
    for dia, patches in sorted(por_data.items()):
        if not patches:
            raise ValueError("Data sem candidatos P1")
        if escolhido is None:
            atual = min(patches, key=lambda p: p.rank)
            metodo, inter_max, dist_min, n_empate, intervalo = (
                "inicial_maior_area", None, None, 1, None)
        else:
            intervalo = (date.fromisoformat(dia)-date.fromisoformat(data_anterior)).days
            if intervalo <= 0:
                raise ValueError("Datas fora de ordem")
            escores = [(p, escolhido.geometria.intersection(p.geometria).area)
                       for p in patches]
            max_overlap = max(score for _, score in escores)
            if max_overlap > 1e-6:
                empatados = [p for p, score in escores if isclose(
                    score, max_overlap, rel_tol=1e-10, abs_tol=1e-6)]
                atual = min(empatados, key=lambda p: p.rank)
                metodo, inter_max, dist_min, n_empate = (
                    "sobreposicao", max_overlap/1e6, None, len(empatados))
            else:
                distancias = [(p, escolhido.geometria.distance(p.geometria))
                              for p in patches]
                menor = min(dist for _, dist in distancias)
                empatados = [p for p, dist in distancias if isclose(
                    dist, menor, rel_tol=1e-10, abs_tol=1e-6)]
                atual = min(empatados, key=lambda p: p.rank)
                metodo, inter_max, dist_min, n_empate = (
                    "distancia_fallback", 0.0, menor/1000, len(empatados))
        linhas.append({
            "id_incendio": atual.incendio, "data": dia,
            "dias_intervalo": intervalo, "rank_p2_exportado": ranks_p2[dia],
            "rank_reproduzido": atual.rank, "confere": atual.rank == ranks_p2[dia],
            "criterio_reproduzido": metodo,
            "area_intersecao_maxima_km2": inter_max,
            "distancia_minima_fallback_km": dist_min,
            "empate_melhor_escore": n_empate > 1,
            "numero_componentes_p1": len(patches),
        })
        escolhido, data_anterior = atual, dia
    return linhas


def analisar(por_data: dict[str, list[Patch]],
            geometrias_originais: dict[str, object], ranks_p2: dict[str, int],
            projecao: dict):
    """Retorna tabelas, cinco linhas GeoJSON e contagens para auditoria."""
    dias = sorted(por_data)
    if not dias:
        raise ValueError("Nenhuma observacao")
    crs = pyproj.CRS.from_proj4(projecao["definicao_laea_proj4"])
    proj = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    inv = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    geod = pyproj.Geod(ellps="WGS84")
    mapa_patches = {(p.data, p.rank): p for grupo in por_data.values() for p in grupo}
    selecionados = {}
    pontos_por_data = {}
    tabela_pontos = []
    for dia in dias:
        if dia not in geometrias_originais or dia not in ranks_p2:
            raise ValueError(f"P2 sem geometria/rank no dia {dia}")
        patch = mapa_patches[(dia, ranks_p2[dia])]
        selecionados[dia] = patch
        pts = pontos_cardeais(geometrias_originais[dia], patch.geometria, proj, inv)
        pontos_por_data[dia] = pts
        for nome in PONTOS:
            (lon, lat), (x, y), empates = pts[nome]
            tabela_pontos.append({"id_incendio": patch.incendio, "data": dia,
                                  "rank_p2": patch.rank, "ponto": nome,
                                  "longitude": lon, "latitude": lat,
                                  "x_laea_m": x, "y_laea_m": y,
                                  "empates_extremo": empates})
    tabela_feixes, tabela_regiao = [], []
    for dia0, dia1 in zip(dias, dias[1:]):
        intervalo = (date.fromisoformat(dia1)-date.fromisoformat(dia0)).days
        for nome in PONTOS:
            (ll0, xy0, _), (ll1, xy1, _) = (
                pontos_por_data[dia0][nome], pontos_por_data[dia1][nome])
            dist, azi = distancia_direcao(geod, ll0, ll1)
            dx, dy = (xy1[0]-xy0[0])/1000, (xy1[1]-xy0[1])/1000
            delta_eixo = {"centroide": None, "norte": dy, "sul": -dy,
                          "leste": dx, "oeste": -dx}[nome]
            tabela_feixes.append({
                "id_incendio": selecionados[dia1].incendio,
                "data_anterior": dia0, "data_atual": dia1,
                "dias_intervalo": intervalo, "ponto": nome,
                "distancia_geodesica_km": dist,
                "azimute_geodesico_graus": azi,
                "delta_x_laea_km": dx,
                "delta_y_laea_km": dy,
                "delta_eixo_orientado_km": delta_eixo,
                "distancia_media_km_dia": dist/intervalo,
            })
        pol = indicadores_poligono(selecionados[dia0], selecionados[dia1], intervalo)
        centro = tabela_feixes[-5]
        tabela_regiao.append({
            "id_incendio": selecionados[dia1].incendio,
            "data_anterior": dia0, "data_atual": dia1,
            "dias_intervalo": intervalo,
            "rank_anterior": selecionados[dia0].rank,
            "rank_atual": selecionados[dia1].rank,
            **pol,
            "deslocamento_centroide_km": centro["distancia_geodesica_km"],
            "azimute_centroide_graus": centro["azimute_geodesico_graus"],
            "numero_componentes_p1_anterior": len(por_data[dia0]),
            "numero_componentes_p1_atual": len(por_data[dia1]),
        })
    trajetorias = []
    for nome in PONTOS:
        coords = [pontos_por_data[dia][nome][0] for dia in dias]
        geometria = mapping(LineString(coords)) if len(coords) > 1 else mapping(Point(coords[0]))
        trajetorias.append({"type": "Feature", "geometry": geometria,
                             "properties": {"ponto": nome,
                                            "id_incendio": selecionados[dias[0]].incendio,
                                            "inicio": dias[0], "fim": dias[-1],
                                            "observacoes": len(dias)}})
    rastreamento = reproduzir_rastreamento(por_data, ranks_p2)
    resumo = {
        "id_incendio": selecionados[dias[0]].incendio,
        "datas": len(dias), "transicoes": len(tabela_regiao),
        "pontos": len(tabela_pontos), "segmentos": len(tabela_feixes),
        "trajetorias": len(trajetorias),
        "ranks_rastreamento_conferem": sum(r["confere"] for r in rastreamento),
        "ranks_rastreamento_divergentes": [r for r in rastreamento if not r["confere"]],
        "transicoes_com_lacuna": [r["data_atual"] for r in tabela_regiao if r["lacuna_temporal"]],
        "criterios_rastreamento": {
            tipo: sum(r["criterio_reproduzido"] == tipo for r in rastreamento)
            for tipo in ("inicial_maior_area", "sobreposicao", "distancia_fallback")
        },
        "empates_rastreamento": [r["data"] for r in rastreamento if r["empate_melhor_escore"]],
        "centroide_deslocamento_acumulado_km": sum(
            r["distancia_geodesica_km"] for r in tabela_feixes if r["ponto"] == "centroide"),
        "abordagem_tr": "trajetorias_representativas_cinco_descritores",
        "comparador_geometrico_p2": "indicadores_da_geometria_integral",
        "abordagem_igt_modulo_separado": "analisar_incrementos_geometricos.py",
    }
    return tabela_pontos, tabela_feixes, tabela_regiao, rastreamento, trajetorias, resumo


def executar(p1: Path, p2: Path, pasta_saida: Path) -> dict:
    """Audita P1/P2, calcula as trajetorias e grava resultados sem alterar fontes."""
    patches = carregar_p1(p1)
    indice = {(p.data, p.rank): p for p in patches}
    projecao, reparados = projetar_patches(patches)
    proj = pyproj.Transformer.from_crs(
        "EPSG:4326", pyproj.CRS.from_proj4(projecao["definicao_laea_proj4"]),
        always_xy=True)
    with p2.open(encoding="utf-8") as arq:
        produto = json.load(arq)
    if produto.get("type") != "FeatureCollection" or not produto.get("features"):
        raise ValueError("P2 deve ser FeatureCollection nao vazia")
    ranks, geoms = {}, {}
    maior_diferenca_p1_p2_m2 = 0.0
    auditorias_p2 = []
    inv = pyproj.Transformer.from_crs(
        pyproj.CRS.from_proj4(projecao["definicao_laea_proj4"]),
        "EPSG:4326", always_xy=True)
    ids = {p.incendio for p in patches}
    for i, feat in enumerate(produto["features"]):
        prop = feat.get("properties") or {}
        try:
            dia = prop["data"]
            date.fromisoformat(dia)
            rank = int(prop["rank_global"])
            incendio = int(prop["id_incendio"])
            geom = shape(feat["geometry"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"P2 registro {i} invalido: {exc}") from exc
        if prop["rank_global"] != rank or prop["id_incendio"] != incendio:
            raise ValueError(f"P2 registro {i}: rank ou ID fracionario")
        if incendio not in ids or (dia, rank) not in indice or dia in ranks:
            raise ValueError(f"P2 registro {i}: ID, rank ou data incoerente/duplicada")
        if geom.geom_type not in ("Polygon", "MultiPolygon") or geom.is_empty:
            raise ValueError(f"P2 registro {i}: geometria nao poligonal")
        # Exportacoes GEE da mesma geometria podem diferir em coordenadas
        # flutuantes; usar equivalencia por area simetrica em metros quadrados.
        gm, auditoria = reconciliar_p2(
            geom, indice[(dia, rank)], proj, registro=i, data=dia, rank=rank,
        )
        auditorias_p2.append(auditoria)
        maior_diferenca_p1_p2_m2 = max(
            maior_diferenca_p1_p2_m2, auditoria["diferenca_simetrica_m2"],
        )
        ranks[dia] = rank
        # Os extremos do TR usam a fonte original enquanto estiver íntegra.
        # Caso o P2 precise reparo, usam a mesma geometria P1 auditada,
        # reprojetada para WGS84: não misturar bases topológicas distintas.
        if auditoria["reparo_p2_necessario"]:
            canonica = shapely.transform(
                indice[(dia, rank)].geometria, inv.transform, interleaved=False,
            )
            if not canonica.is_valid:
                raise ValueError(
                    f"P2 registro {i}: P1 reparado voltou inválido ao WGS84"
                )
            geoms[dia] = canonica
        else:
            geoms[dia] = geom
    por_data = defaultdict(list)
    for patch in patches:
        por_data[patch.data].append(patch)
    if set(por_data) != set(ranks):
        raise ValueError("P1 e P2 devem ter as mesmas datas")
    for grupo in por_data.values():
        grupo.sort(key=lambda p: p.rank)
    tabelas = analisar(por_data, geoms, ranks, projecao)
    pontos, feixes, regiao, rastreamento, trajetorias, resumo = tabelas
    resumo.update({
        "projecao": projecao, "geometrias_reparadas_apos_projecao": reparados,
        "maior_diferenca_simetrica_p1_p2_m2": maior_diferenca_p1_p2_m2,
        "reparos_p2_para_comparacao": [
            d for d in auditorias_p2 if d["reparo_p2_necessario"]
        ],
        "numero_reparos_p2_para_comparacao": sum(
            d["reparo_p2_necessario"] for d in auditorias_p2
        ),
        "criterio_p2": "make_valid condicionado a equivalencia topologica com P1; "
                       "tolerancia max(1m2, 1e-8*area_p1)",
        "sha256_p1": sha256(p1.read_bytes()).hexdigest(),
        "sha256_p2": sha256(p2.read_bytes()).hexdigest(),
        "origem_p1": str(p1), "origem_p2": str(p2),
    })
    pasta_saida.mkdir(parents=True, exist_ok=True)
    eid = resumo["id_incendio"]
    for stem, campos, linhas in (
        ("pontos_representativos", CAMPOS_PONTOS, pontos),
        ("segmentos_trajetorias", CAMPOS_FEIXES, feixes),
        ("indicadores_regiao", CAMPOS_REGIAO, regiao),
        ("verificacao_rastreamento", CAMPOS_RASTREAMENTO, rastreamento),
    ):
        salvar_csv(pasta_saida / f"{stem}_{eid}.csv", campos, linhas)
    (pasta_saida / f"cinco_trajetorias_{eid}.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": trajetorias},
                   ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    (pasta_saida / f"resumo_regiao_movel_{eid}.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return resumo


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("p1", type=Path)
    parser.add_argument("p2", type=Path)
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(executar(args.p1, args.p2, args.saida),
                         ensure_ascii=False, indent=2))
    except (OSError, ValueError, json.JSONDecodeError, pyproj.ProjError) as exc:
        print(f"FALHA: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
