#!/usr/bin/env python3
"""Compara geometria original, make_valid e buffer(0), sem editar entradas.

Os indicadores calculados sobre poligonos invalidos sao apenas referencias
numericas, NAO metricas de paisagem cientificamente aceitas.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from math import pi, sqrt
from pathlib import Path
import statistics

import pyproj
import shapely
from shapely.geometry import shape


def partes_poligonais(geom) -> int:
    if geom.geom_type == "Polygon":
        return 1
    if geom.geom_type == "MultiPolygon":
        return len(geom.geoms)
    if geom.geom_type == "GeometryCollection":
        return sum(partes_poligonais(x) for x in geom.geoms)
    return 0


def estatistica(valores: list[float]) -> dict:
    if not valores:
        return {"n": 0}
    ordenado = sorted(valores)
    return {
        "n": len(valores),
        "mediana": round(statistics.median(ordenado), 7),
        "p95": round(ordenado[int(0.95 * (len(ordenado) - 1))], 7),
        "max": round(ordenado[-1], 7),
    }


def centro_projecao(geoms: list) -> tuple:
    xs = [g.bounds for g in geoms]
    lon0 = (min(a[0] for a in xs) + max(a[2] for a in xs)) / 2
    lat0 = (min(a[1] for a in xs) + max(a[3] for a in xs)) / 2
    crs = pyproj.CRS.from_proj4(
        f"+proj=laea +lat_0={lat0:.10f} +lon_0={lon0:.10f} "
        "+datum=WGS84 +units=m +no_defs"
    )
    return pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True), (lon0, lat0)


def processar(caminho: Path, conversor, fator_area: float | None = None) -> list:
    with caminho.open(encoding="utf-8") as arquivo:
        features = json.load(arquivo)["features"]
    out = []
    for indice, f in enumerate(features):
        prop = f["properties"]
        original_geo = shape(f["geometry"])
        # O ponto principal do experimento e testar a ordem das operacoes:
        # regularizar em coordenadas geografica vs projetar primeiro.
        geo_variantes = {
            "original": original_geo,
            "make_valid": shapely.make_valid(original_geo),
            "buffer_0": original_geo.buffer(0),
        }
        variantes = {}
        reparo_pos_projecao = {}
        for nome, geom in geo_variantes.items():
            projetada = shapely.transform(geom, conversor.transform,
                                         interleaved=False)
            reparo_pos_projecao[nome] = nome != "original" and not projetada.is_valid
            if reparo_pos_projecao[nome]:
                # Diagnostico de dupla regularizacao requerido pela reprojecao.
                projetada = shapely.make_valid(projetada)
            variantes[nome] = projetada
        variantes["make_valid_apos_projecao"] = shapely.make_valid(variantes["original"])
        regularizada = variantes["make_valid"]
        buffer_zero = variantes["buffer_0"]
        original = variantes["original"]
        info = {
            "indice": indice,
            "data": prop["data"],
            "rank": int(prop.get("rank_global", prop.get("rank", -1))),
            "area_atributo_km2": float(prop["area_km2"]),
            "original_valida": original_geo.is_valid,
            "original_projetada_valida": original.is_valid,
            "variantes": {},
        }
        for nome, geom in variantes.items():
            area = geom.area / 1e6
            perimetro = geom.length / 1000
            info["variantes"][nome] = {
                "valida": (geo_variantes[nome].is_valid
                           if nome in geo_variantes else geom.is_valid),
                "valida_projetada": geom.is_valid,
                "reparo_adicional_apos_projecao": reparo_pos_projecao.get(nome, False),
                "vazia": geom.is_empty,
                "tipo": geom.geom_type,
                "n_partes": partes_poligonais(geom),
                "area_km2": area,
                "perimetro_km": perimetro,
                "shape_index": perimetro / (2 * sqrt(pi * area)) if area > 0 else None,
            }
            if fator_area:
                refer = info["area_atributo_km2"] * fator_area
                info["variantes"][nome]["erro_area_ajustado_pct"] = (
                    100 * (area / refer - 1) if refer else None
                )
        if original_geo.is_valid:
            # O proprio experimento confere que variantes nao mudam validos.
            info["original_mantida"] = True
        else:
            area_mv = regularizada.area
            info["perda_buffer_versus_make_valid_pct"] = (
                100 * (area_mv - buffer_zero.area) / area_mv if area_mv else None
            )
            info["distancia_centroides_original_make_valid_m"] = (
                original.centroid.distance(regularizada.centroid)
            )
            info["fracao_diferenca_buffer_make_valid"] = (
                regularizada.symmetric_difference(buffer_zero).area /
                regularizada.union(buffer_zero).area
                if regularizada.union(buffer_zero).area else 0.0
            )
        out.append(info)
    return out


def agregar(feicoes: list, fator: float) -> dict:
    invalidos = [x for x in feicoes if not x["original_valida"]]
    metodos = {}
    for nome in ("original", "make_valid", "buffer_0", "make_valid_apos_projecao"):
        v = [x["variantes"][nome] for x in feicoes]
        vi = [x["variantes"][nome] for x in invalidos]
        desvios = [abs(y["erro_area_ajustado_pct"])
                   for y in v if y.get("erro_area_ajustado_pct") is not None]
        desvios_invalidos = [abs(y["erro_area_ajustado_pct"])
                            for y in vi if y.get("erro_area_ajustado_pct") is not None]
        metodos[nome] = {
            "validas": sum(y["valida"] for y in v),
            "validas_apos_projecao": sum(y["valida_projetada"] for y in v),
            "reparos_adicionais_apos_projecao": sum(
                y["reparo_adicional_apos_projecao"] for y in v),
            "vazias": sum(y["vazia"] for y in v),
            "partes_poligonais_total": sum(y["n_partes"] for y in v),
            "feicoes_multipartes": sum(y["n_partes"] > 1 for y in v),
            "feicoes_erro_area_ajustado_acima_1pct": sum(x > 1 for x in desvios),
            "erro_absoluto_area_ajustado_pct": estatistica(desvios),
            "erro_absoluto_area_ajustado_invalidos_pct": estatistica(desvios_invalidos),
        }
    mudancas_mv = []
    mudancas_b0 = []
    mudancas_shape_mv = []
    mudancas_area_mv = []
    mudancas_area_b0 = []
    for f in invalidos:
        ori = f["variantes"]["original"]
        for nome, destino in (("make_valid", mudancas_mv), ("buffer_0", mudancas_b0)):
            c = f["variantes"][nome]
            destino.append(100 * (c["perimetro_km"] / ori["perimetro_km"] - 1))
        if ori["area_km2"]:
            mudancas_area_mv.append(100 * (
                f["variantes"]["make_valid"]["area_km2"] / ori["area_km2"] - 1
            ))
            mudancas_area_b0.append(100 * (
                f["variantes"]["buffer_0"]["area_km2"] / ori["area_km2"] - 1
            ))
        shape_ori = ori["shape_index"]
        shape_mv = f["variantes"]["make_valid"]["shape_index"]
        if shape_ori and shape_mv:
            mudancas_shape_mv.append(100 * (shape_mv / shape_ori - 1))
    pior_perda = sorted(
        invalidos,
        key=lambda f: f["perda_buffer_versus_make_valid_pct"] or 0,
        reverse=True,
    )[:12]
    pior_erro_original = sorted(
        invalidos,
        key=lambda f: abs(f["variantes"]["original"]["erro_area_ajustado_pct"]),
        reverse=True,
    )[:12]
    por_data = defaultdict(list)
    for f in feicoes:
        por_data[f["data"]].append(f)
    datas = sorted(por_data)
    impacto_diario = []
    for dia in datas:
        lista = por_data[dia]
        area_mv = sum(x["variantes"]["make_valid"]["area_km2"] for x in lista)
        area_b0 = sum(x["variantes"]["buffer_0"]["area_km2"] for x in lista)
        impacto_diario.append({
            "data": dia,
            "area_make_valid_km2": round(area_mv, 6),
            "area_buffer_0_km2": round(area_b0, 6),
            "perda_buffer_0_km2": round(area_mv - area_b0, 6),
            "perda_buffer_0_pct": round(100 * (area_mv - area_b0) / area_mv, 6),
            "n_registros": len(lista),
            "n_partes_make_valid": sum(x["variantes"]["make_valid"]["n_partes"]
                                        for x in lista),
        })
    return {
        "total": len(feicoes),
        "invalidos_original": len(invalidos),
        "fator_calibracao_area_entre_sistemas": round(fator, 10),
        "comparacao": metodos,
        "variacao_perimetro_invalidos_pct": {
            "make_valid": estatistica(mudancas_mv),
            "buffer_0": estatistica(mudancas_b0),
            "make_valid_valor_absoluto": estatistica([abs(x) for x in mudancas_mv]),
        },
        "variacao_area_invalidos_pct": {
            "make_valid": estatistica(mudancas_area_mv),
            "buffer_0": estatistica(mudancas_area_b0),
            "make_valid_valor_absoluto": estatistica([abs(x) for x in mudancas_area_mv]),
            "buffer_0_valor_absoluto": estatistica([abs(x) for x in mudancas_area_b0]),
        },
        "variacao_shape_index_make_valid_invalidos_pct": estatistica(mudancas_shape_mv),
        "perda_buffer_versus_make_valid_pct": estatistica([
            x["perda_buffer_versus_make_valid_pct"] for x in invalidos
            if x["perda_buffer_versus_make_valid_pct"] is not None
        ]),
        "deslocamento_centroide_make_valid_m": estatistica([
            x["distancia_centroides_original_make_valid_m"] for x in invalidos
        ]),
        "piores_perdas_buffer_0": [
            {"data": x["data"], "rank": x["rank"],
             "perda_area_pct": round(x["perda_buffer_versus_make_valid_pct"], 4),
             "area_make_valid_km2": round(x["variantes"]["make_valid"]["area_km2"], 5),
             "n_partes_make_valid": x["variantes"]["make_valid"]["n_partes"],
             "n_partes_buffer_0": x["variantes"]["buffer_0"]["n_partes"]}
            for x in pior_perda
        ],
        "piores_erros_area_original": [
            {"data": x["data"], "rank": x["rank"],
             "erro_area_original_pct": round(
                 x["variantes"]["original"]["erro_area_ajustado_pct"], 4)}
            for x in pior_erro_original
        ],
        "maior_impacto_diario_buffer_0": max(
            impacto_diario, key=lambda x: x["perda_buffer_0_km2"]),
        "ultima_data": impacto_diario[-1],
    }


def comparar(p1_path: Path, p2_path: Path) -> dict:
    with p1_path.open(encoding="utf-8") as arquivo:
        f1 = json.load(arquivo)["features"]
    geoms1 = [shape(x["geometry"]) for x in f1]
    conversor, centro = centro_projecao(geoms1)
    with p2_path.open(encoding="utf-8") as arquivo:
        geoms2 = [shape(x["geometry"]) for x in json.load(arquivo)["features"]]
    proj_utm = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32721", always_xy=True)
    proj_global = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True)

    def invalidos_por_crs(geoms: list) -> dict:
        return {
            "origem_lonlat": sum(not g.is_valid for g in geoms),
            "laea_local": sum(not shapely.transform(
                g, conversor.transform, interleaved=False).is_valid for g in geoms),
            "utm_21s_epsg32721": sum(not shapely.transform(
                g, proj_utm.transform, interleaved=False).is_valid for g in geoms),
            "cea_global_epsg6933": sum(not shapely.transform(
                g, proj_global.transform, interleaved=False).is_valid for g in geoms),
        }
    # A comparacao sistematica entre esferas/elipsoides nao e uma medida de
    # erro real: normalizamos pelo fator mediano observado em feicoes validas.
    p1_tmp = processar(p1_path, conversor)
    fatores = [x["variantes"]["original"]["area_km2"] / x["area_atributo_km2"]
               for x in p1_tmp if x["original_valida"] and x["area_atributo_km2"] > 0]
    fator = statistics.median(fatores)
    p1 = processar(p1_path, conversor, fator)
    p2 = processar(p2_path, conversor, fator)
    return {
        "objetivo": "Sensibilidade de medidas geometricas ao metodo de regularizacao",
        "aviso": "Proposta diagnostica, nao criterio definitivo de conectividade",
        "shapely": shapely.__version__,
        "pyproj": pyproj.__version__,
        "crs_metricas": "LAEA local sobre WGS84",
        "centro_lonlat": [round(x, 8) for x in centro],
        "validade_por_crs": {
            "p1": invalidos_por_crs(geoms1),
            "p2": invalidos_por_crs(geoms2),
        },
        "p1": agregar(p1, fator),
        "p2": agregar(p2, fator),
    }


def main() -> int:
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument("p1", type=Path)
    arg.add_argument("p2", type=Path)
    arg.add_argument("--saida-json", type=Path)
    args = arg.parse_args()
    resultado = comparar(args.p1, args.p2)
    if args.saida_json:
        args.saida_json.parent.mkdir(parents=True, exist_ok=True)
        args.saida_json.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
    print(json.dumps({nome: {
        "invalidos_original": resultado[nome]["invalidos_original"],
        "comparacao": resultado[nome]["comparacao"],
        "perda_buffer_versus_make_valid_pct": resultado[nome]["perda_buffer_versus_make_valid_pct"],
    } for nome in ("p1", "p2")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
