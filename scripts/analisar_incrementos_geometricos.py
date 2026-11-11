#!/usr/bin/env python3
"""Calcula incrementos geometricos temporais (IGT) de uma regiao P2 acumulada.

Usa os mesmos dados e LAEA local das etapas anteriores. A diferenca temporal
R(t+1) \\ R(t) descreve area queimada detectada, nao frente ativa do fogo.
O algoritmo e uma implementacao operacional do organograma fornecido;
a equivalencia com artigo externo depende de verificacao bibliografica.
"""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from math import atan2, cos, degrees, hypot, radians, sin
from pathlib import Path
import sys

import pyproj
import shapely
from shapely.geometry import mapping, shape

from calcular_metricas_paisagem import carregar_p1, projetar_patches, salvar_csv


CAMPOS_INTERVALOS = [
    "id_incendio", "data_anterior", "data_atual", "dias_intervalo",
    "area_anterior_km2", "area_atual_km2", "area_nova_km2",
    "area_perdida_km2", "incremento_liquido_km2", "numero_componentes_incremento",
    "maior_componente_incremento_km2", "fracao_maior_componente",
    "azimute_medio_ponderado_graus", "concentracao_direcional",
    "erro_fechamento_area_m2", "erro_soma_componentes_m2", "lacuna_temporal",
]
CAMPOS_COMPONENTES = [
    "id_incendio", "data_anterior", "data_atual", "componente_rank",
    "area_km2", "centroide_longitude", "centroide_latitude",
    "azimute_incremento_graus", "fracao_area_incremento",
]


def partes_poligonais(geom):
    """Desmembra polígonos sem colapsar separações nem ignorar ilhas pequenas."""
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom] if geom.area > 0 else []
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [p for g in geom.geoms for p in partes_poligonais(g)]
    raise ValueError(f"Diferenca nao poligonal: {geom.geom_type}")


def calcular_incremento(anterior, atual, inv, geod, *, evento, dia0, dia1):
    """Calculo independente para uma transicao com CRS metricos de area igual."""
    dias = (date.fromisoformat(dia1) - date.fromisoformat(dia0)).days
    if dias <= 0:
        raise ValueError("Datas invalidas ou repetidas")
    if any(g.is_empty or not g.is_valid or g.area <= 0 for g in (anterior, atual)):
        raise ValueError("Geometrias devem ser validas, positivas e nao vazias")

    nova = atual.difference(anterior)
    perdida = anterior.difference(atual)
    componentes = partes_poligonais(nova)
    componentes.sort(key=lambda g: (-g.area, g.centroid.x, g.centroid.y))
    x0, y0 = anterior.centroid.x, anterior.centroid.y
    lon0, lat0 = inv.transform(x0, y0)
    linhas_componentes, vetor_x, vetor_y = [], 0.0, 0.0
    for rank, parte in enumerate(componentes, start=1):
        centro = parte.centroid
        lon, lat = inv.transform(centro.x, centro.y)
        azimute, _, distancia_m = geod.inv(lon0, lat0, lon, lat)
        az = azimute % 360 if distancia_m > 1e-6 else None
        if az is not None:
            vetor_x += parte.area * sin(radians(az))
            vetor_y += parte.area * cos(radians(az))
        linhas_componentes.append({
            "id_incendio": evento, "data_anterior": dia0, "data_atual": dia1,
            "componente_rank": rank, "area_km2": parte.area / 1e6,
            "centroide_longitude": lon, "centroide_latitude": lat,
            "azimute_incremento_graus": az,
            "fracao_area_incremento": parte.area / nova.area if nova.area else None,
        })

    modulo = hypot(vetor_x, vetor_y)
    concentracao = modulo / nova.area if nova.area > 0 else None
    # Vetores quase opostos produzem angulo espurio por arredondamento.
    # O limite de 1% e limiar operacional explicito, nao precisao do sensor.
    az_medio = (degrees(atan2(vetor_x, vetor_y)) % 360
                if concentracao is not None and concentracao >= .01 else None)
    linha = {
        "id_incendio": evento, "data_anterior": dia0, "data_atual": dia1,
        "dias_intervalo": dias, "area_anterior_km2": anterior.area / 1e6,
        "area_atual_km2": atual.area / 1e6, "area_nova_km2": nova.area / 1e6,
        "area_perdida_km2": perdida.area / 1e6,
        "incremento_liquido_km2": (atual.area-anterior.area) / 1e6,
        "numero_componentes_incremento": len(componentes),
        "maior_componente_incremento_km2": componentes[0].area / 1e6 if componentes else 0,
        "fracao_maior_componente": componentes[0].area/nova.area if nova.area else None,
        "azimute_medio_ponderado_graus": az_medio,
        "concentracao_direcional": concentracao,
        "erro_fechamento_area_m2": abs((nova.area-perdida.area)-(atual.area-anterior.area)),
        "erro_soma_componentes_m2": abs(sum(c.area for c in componentes)-nova.area),
        "lacuna_temporal": dias > 1,
    }
    return linha, linhas_componentes, nova


def executar(p1: Path, p2: Path, saida: Path) -> dict:
    patches = carregar_p1(p1)
    projecao, reparados = projetar_patches(patches)
    if reparados:
        raise ValueError("IGT exige P1 valido sem reparos implicitos")
    indice = {(p.data, p.rank): p for p in patches}
    ids = {p.incendio for p in patches}
    if len(ids) != 1:
        raise ValueError("Um arquivo por ID; SQL permite varios IDs na tabela")
    evento = ids.pop()
    crs = pyproj.CRS.from_proj4(projecao["definicao_laea_proj4"])
    proj = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    inv = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    with p2.open(encoding="utf-8") as arquivo:
        produto = json.load(arquivo)
    if produto.get("type") != "FeatureCollection" or not produto.get("features"):
        raise ValueError("P2 vazio ou fora do padrao FeatureCollection")
    selecionados = {}
    for i, feat in enumerate(produto["features"]):
        prop = feat.get("properties") or {}
        try:
            dia, rank, id_lido = prop["data"], int(prop["rank_global"]), int(prop["id_incendio"])
            date.fromisoformat(dia)
            original = shape(feat["geometry"])
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"P2 registro {i} invalido") from exc
        if id_lido != evento or (dia, rank) not in indice or dia in selecionados:
            raise ValueError(f"P2 registro {i}: ID, rank ou data incoerente")
        if prop["rank_global"] != rank or prop["id_incendio"] != id_lido:
            raise ValueError(f"P2 registro {i}: rank ou ID fracionario")
        geom_laea = shapely.transform(original, proj.transform, interleaved=False)
        if not geom_laea.is_valid or geom_laea.is_empty:
            raise ValueError(f"P2 registro {i}: geometria invalida")
        geometria_p1 = indice[(dia, rank)].geometria
        diferenca = geom_laea.symmetric_difference(geometria_p1).area
        if diferenca > max(1., geometria_p1.area*1e-8):
            raise ValueError(f"P2 registro {i}: diverge de P1")
        selecionados[dia] = geometria_p1  # mesmo referencial dos resultados anteriores
    if set(selecionados) != {p.data for p in patches}:
        raise ValueError("Datas P1 e P2 nao coincidem")
    dias = sorted(selecionados)
    geod = pyproj.Geod(ellps="WGS84")
    intervalos, componentes, feicoes = [], [], []
    for dia0, dia1 in zip(dias, dias[1:]):
        linha, partes, incremento = calcular_incremento(
            selecionados[dia0], selecionados[dia1], inv, geod,
            evento=evento, dia0=dia0, dia1=dia1,
        )
        intervalos.append(linha)
        componentes.extend(partes)
        feicoes.append({"type": "Feature", "properties": {
            "id_incendio": evento, "data_anterior": dia0, "data_atual": dia1,
            "area_nova_km2": linha["area_nova_km2"],
            "numero_componentes": linha["numero_componentes_incremento"]},
            "geometry": mapping(shapely.transform(incremento, inv.transform,
                                                   interleaved=False))})
    if any(r["erro_fechamento_area_m2"] > 1.0 or
           r["erro_soma_componentes_m2"] > 1.0 for r in intervalos):
        raise ValueError("Invariantes de area do IGT excederam 1 m2")
    resumo = {
        "id_incendio": evento, "abordagem": "IGT_incrementos_geometricos_temporais",
        "observacoes": len(dias), "transicoes": len(intervalos),
        "componentes_incremento": len(componentes),
        "area_nova_total_km2": sum(r["area_nova_km2"] for r in intervalos),
        "area_perdida_total_km2": sum(r["area_perdida_km2"] for r in intervalos),
        "incremento_liquido_total_km2": sum(r["incremento_liquido_km2"] for r in intervalos),
        "max_erro_fechamento_area_m2": max((r["erro_fechamento_area_m2"] for r in intervalos), default=0),
        "max_erro_soma_componentes_m2": max((r["erro_soma_componentes_m2"] for r in intervalos), default=0),
        "lacunas_temporais": [r["data_atual"] for r in intervalos if r["lacuna_temporal"]],
        "projecao": projecao, "sha256_p1": sha256(p1.read_bytes()).hexdigest(),
        "sha256_p2": sha256(p2.read_bytes()).hexdigest(),
        "sql_postgis_executado": False,
        "comparabilidade_sql": "equivalencia logica; diferenca planar WGS84 no SQL vs LAEA no Python",
    }
    saida.mkdir(parents=True, exist_ok=True)
    salvar_csv(saida / f"incrementos_temporais_{evento}.csv", CAMPOS_INTERVALOS, intervalos)
    salvar_csv(saida / f"componentes_incrementos_{evento}.csv", CAMPOS_COMPONENTES, componentes)
    (saida / f"geometrias_incrementos_{evento}.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feicoes},
                   ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    (saida / f"resumo_incrementos_{evento}.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return resumo


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("p1", type=Path)
    parser.add_argument("p2", type=Path)
    parser.add_argument("--saida", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(executar(args.p1, args.p2, args.saida),
                         ensure_ascii=False, indent=2))
    except (ValueError, OSError, json.JSONDecodeError, pyproj.ProjError) as exc:
        print(f"FALHA: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
