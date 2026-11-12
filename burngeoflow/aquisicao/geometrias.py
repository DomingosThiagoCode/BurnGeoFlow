"""Diagnóstico e normalização AUDITÁVEL de geometrias GeoJSON do GEE.

Polygon/MultiPolygon são mantidos. GeometryCollection é convertida apenas quando
contém subgeometrias poligonais. Feições estritamente não areais só são
excluídas se a área reportada for rigorosamente nula (<= 1e-12 km²).
Todas as decisões são documentadas e os GeoJSON brutos são preservados.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from math import isfinite


class ErroGeometria(RuntimeError):
    pass


def _poligonos(geom: dict) -> tuple[list[list], list[str]]:
    tipo = geom.get("type")
    if tipo == "Polygon":
        coords = geom.get("coordinates")
        return ([coords] if coords else []), []
    if tipo == "MultiPolygon":
        return list(geom.get("coordinates") or []), []
    if tipo == "GeometryCollection":
        encontrados = []
        ignorados = []
        for g in geom.get("geometries", []):
            if not isinstance(g, dict):
                ignorados.append("inválida")
                continue
            pg, outros = _poligonos(g)
            encontrados.extend(pg)
            ignorados.extend(outros)
        return encontrados, ignorados
    return [], [str(tipo)]


def diagnosticar(fc: dict, rotulo: str) -> dict:
    tipos = Counter()
    nao_poligonais = []
    for i, feat in enumerate(fc.get("features", [])):
        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}
        tipo = geom.get("type") or "sem_geometria"
        tipos[tipo] += 1
        if tipo not in {"Polygon", "MultiPolygon"} or not geom.get("coordinates"):
            polys, extras = _poligonos(geom)
            nao_poligonais.append({
                "indice": i, "tipo": tipo,
                "data": props.get("data"), "rank": props.get("rank"),
                "area_km2": props.get("area_km2"),
                "partes_poligonais": len(polys),
                "partes_nao_poligonais": extras,
            })
    return {
        "produto": rotulo,
        "total": len(fc.get("features", [])),
        "tipos_geometricos": dict(sorted(tipos.items())),
        "feicoes_para_revisao": nao_poligonais,
    }


def normalizar_produtos(p1: dict, p2: dict) -> tuple[dict, dict, dict]:
    """Normaliza ou exclui apenas artefatos sem dimensão de área.

    Ranks e número de componentes são corrigidos após eventuais exclusões.
    Se uma feição não poligonal tiver área positiva, ABORTA sem alterar dados.
    """
    originais = {"P1": p1, "P2": p2}
    relatorio = {
        "inspecao_brutos": {nome: diagnosticar(fc, nome) for nome, fc in originais.items()},
        "geometrias_convertidas": [],
        "sem_area_excluidos": [],
        "inconsistencias": [],
        "politica": "converter GeometryCollection poligonal; excluir apenas nao-area com area_km2 nula; manter brutos",
    }
    normalizados = {}
    for nome, bruto in originais.items():
        fc = {"type": "FeatureCollection", "features": []}
        for indice, feat in enumerate(bruto.get("features", [])):
            feat = deepcopy(feat)
            geom = feat.get("geometry")
            props = feat.get("properties") or {}
            tipo = (geom or {}).get("type")
            if not isinstance(geom, dict):
                polys, extras = [], ["sem_geometria"]
            else:
                polys, extras = _poligonos(geom)
            if tipo in {"Polygon", "MultiPolygon"} and polys:
                fc["features"].append(feat)
                continue
            registro = {
                "produto": nome, "indice": indice, "tipo_original": tipo,
                "data": props.get("data"), "rank": props.get("rank"),
                "area_km2": props.get("area_km2"),
            }
            if polys:
                feat["geometry"] = (
                    {"type": "Polygon", "coordinates": polys[0]}
                    if len(polys) == 1 else
                    {"type": "MultiPolygon", "coordinates": polys}
                )
                registro.update({
                    "tipo_final": feat["geometry"]["type"],
                    "partes_poligonais": len(polys),
                    "partes_sem_area": extras,
                })
                relatorio["geometrias_convertidas"].append(registro)
                fc["features"].append(feat)
                continue
            area = props.get("area_km2")
            if (isinstance(area, (float, int)) and not isinstance(area, bool)
                    and isfinite(area) and 0 <= area <= 1e-12):
                relatorio["sem_area_excluidos"].append(registro)
                continue
            relatorio["inconsistencias"].append(registro)
        normalizados[nome] = fc

    if relatorio["inconsistencias"]:
        problema = relatorio["inconsistencias"][0]
        raise ErroGeometria(
            "Geometria nao poligonal com area positiva/desconhecida: "
            f"{problema}. Consulte diagnostico_geometrias.json; brutos preservados."
        )

    eliminados = relatorio["sem_area_excluidos"]
    if eliminados:
        por_data = defaultdict(list)
        for feat in normalizados["P1"]["features"]:
            por_data[feat["properties"]["data"]].append(feat)
        correspondencia = {}
        totais = {}
        for data, feats in por_data.items():
            feats.sort(key=lambda f: int(f["properties"]["rank"]))
            if not feats:
                raise ErroGeometria(f"Nenhum poligono na data {data}.")
            total = sum(float(f["properties"]["area_km2"]) for f in feats)
            totais[data] = total
            mapping = {}
            for indice, feat in enumerate(feats, start=1):
                prop = feat["properties"]
                rank_anterior = int(prop["rank"])
                mapping[rank_anterior] = indice
                prop.update({
                    "rank": indice,
                    "eh_maior": indice == 1,
                    "numero_componentes": len(feats),
                    "area_total_km2": total,
                    "proporcao_area_pct": 100 * float(prop["area_km2"]) / total,
                })
            correspondencia[data] = mapping
        for feat in normalizados["P2"]["features"]:
            prop = feat["properties"]
            data = prop["data"]
            antigo = int(prop["rank_global"])
            if data not in correspondencia or antigo not in correspondencia[data]:
                raise ErroGeometria(
                    f"P2 em {data} nao possui componente areal correspondente no P1."
                )
            novo = correspondencia[data][antigo]
            prop.update({
                "rank": novo,
                "rank_global": novo,
                "rm_eh_maior": novo == 1,
                "numero_componentes": len(por_data[data]),
                "area_total_km2": totais[data],
                "proporcao_rm_pct": 100 * float(prop["area_km2"]) / totais[data],
            })
        datas = sorted(por_data)
        for indice, data in enumerate(datas):
            prev = datas[indice - 1] if indice else None
            prop = next(
                f["properties"] for f in normalizados["P2"]["features"]
                if f["properties"]["data"] == data
            )
            prop["delta_area_total_km2"] = totais[data] - (totais[prev] if prev else totais[data])
            prop["delta_num_componentes"] = (
                len(por_data[data]) - (len(por_data[prev]) if prev else len(por_data[data]))
            )
        relatorio["ranks_atualizados"] = True
    else:
        relatorio["ranks_atualizados"] = False
    relatorio["quantidades_finais"] = {
        nome: len(fc["features"]) for nome, fc in normalizados.items()
    }
    return normalizados["P1"], normalizados["P2"], relatorio
