#!/usr/bin/env python3
"""Auditoria espacial *diagnostica* de P1/P2, sem alterar GeoJSONs.

O objetivo e localizar anomalias reproduziveis antes de definir tolerancias
cientificas. Primeiro reprojeta os vertices originais para LAEA local,
depois valida a geometria. make_valid() e aplicado somente em memoria e
somente se a geometria ainda for invalida APOS a projecao. Nunca se
substitui a geometria original. A validade planar em lon/lat e registrada
separadamente, pois depende do sistema de coordenadas.

Requer shapely e pyproj (ver requirements-auditoria.txt).
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import statistics
import sys

import pyproj
import shapely
from shapely import STRtree, make_valid
from shapely.geometry import shape
from shapely.ops import unary_union
from shapely.validation import explain_validity


# Somente limiares de deteccao diagnostica, NAO tolerancias finais de pesquisa.
LIMIAR_INTERSECAO_M2 = 1.0
LIMIAR_DIFERENCA_RELATIVA = 1e-8
LIMIAR_PERDA_RELEVANTE_M2 = 100.0


@dataclass
class Feicao:
    indice: int
    data: str
    rank: int
    propriedades: dict
    geometria: object
    valida: bool
    motivo_invalidez: str | None
    geometria_diagnostica: object
    metrico: object | None = None
    valida_metrica: bool | None = None
    motivo_invalidez_metrica: str | None = None
    reparo_apos_projecao: bool = False


def ler(caminho: Path) -> list[Feicao]:
    with caminho.open(encoding="utf-8") as arquivo:
        colecao = json.load(arquivo)
    if colecao.get("type") != "FeatureCollection":
        raise ValueError(f"{caminho} nao e FeatureCollection")
    resultado = []
    for indice, feicao in enumerate(colecao["features"]):
        propriedades = feicao["properties"]
        geometria = shape(feicao["geometry"])
        valida = bool(geometria.is_valid)
        resultado.append(Feicao(
            indice=indice,
            data=propriedades["data"],
            rank=int(propriedades.get("rank_global", propriedades.get("rank", -1))),
            propriedades=propriedades,
            geometria=geometria,
            valida=valida,
            motivo_invalidez=None if valida else explain_validity(geometria),
            geometria_diagnostica=geometria,
        ))
    return resultado


def preparar_metrico(p1: list[Feicao], p2: list[Feicao]) -> dict:
    """Projeta para LAEA local, com centro definido pelo proprio evento."""
    limites = [f.geometria.bounds for f in p1]
    oeste = min(b[0] for b in limites)
    sul = min(b[1] for b in limites)
    leste = max(b[2] for b in limites)
    norte = max(b[3] for b in limites)
    lon0 = (oeste + leste) / 2
    lat0 = (sul + norte) / 2
    proj = pyproj.CRS.from_proj4(
        f"+proj=laea +lat_0={lat0:.10f} +lon_0={lon0:.10f} "
        "+datum=WGS84 +units=m +no_defs"
    )
    conversor = pyproj.Transformer.from_crs("EPSG:4326", proj, always_xy=True)
    for f in p1 + p2:
        # A reprojecao pode alterar ligeiramente intersecoes entre segmentos.
        # Validamos novamente a geometria projetada antes de fazer overlay.
        convertido = shapely.transform(f.geometria,
                                       conversor.transform, interleaved=False)
        f.valida_metrica = bool(convertido.is_valid)
        f.motivo_invalidez_metrica = (
            None if f.valida_metrica else explain_validity(convertido))
        f.reparo_apos_projecao = not f.valida_metrica
        f.metrico = convertido if f.valida_metrica else make_valid(convertido)
        f.geometria_diagnostica = f.metrico
    return {"proj": "LAEA local / WGS84", "centro_lon": round(lon0, 8),
            "centro_lat": round(lat0, 8), "limites_lonlat": [oeste, sul, leste, norte]}


def amostra(f: Feicao) -> dict:
    return {"indice": f.indice, "data": f.data, "rank": f.rank}


def resumo_geometrias(feicoes: list[Feicao]) -> dict:
    if any(f.valida_metrica is None for f in feicoes):
        raise ValueError("Projecao metrica deve ser preparada antes do resumo")
    invalidas = [f for f in feicoes if not f.valida]
    motivos = Counter(f.motivo_invalidez.split("[")[0] for f in invalidas)
    tipos = Counter(f.geometria.geom_type for f in feicoes)
    reparadas = [f for f in feicoes if f.reparo_apos_projecao]
    repartidas = [f for f in reparadas
                  if f.geometria_diagnostica.geom_type == "MultiPolygon"]
    return {
        "total": len(feicoes),
        "tipos": dict(sorted(tipos.items())),
        "vazias": sum(f.geometria.is_empty for f in feicoes),
        "invalidas_planas_em_lonlat": len(invalidas),
        "tipos_invalidez_planar_lonlat": dict(sorted(motivos.items())),
        "datas_com_invalidez_planar_lonlat": len({f.data for f in invalidas}),
        "invalidas_apos_projecao_laea": len(reparadas),
        "reparos_condicionais_apos_projecao": len(reparadas),
        "reparos_geraram_multipolygon": len(repartidas),
        "max_partes_no_reparo": int(max(
            (shapely.get_num_geometries(f.geometria_diagnostica)
             for f in repartidas), default=1)),
        "amostras_invalidas_planas_lonlat": [
            dict(amostra(f), motivo=f.motivo_invalidez) for f in invalidas[:12]],
        "amostras_invalidas_apos_projecao": [
            dict(amostra(f), motivo=f.motivo_invalidez_metrica)
            for f in reparadas[:12]],
    }


def resumo_areas(feicoes: list[Feicao]) -> dict:
    """Compara atributos publicados com area equivalente elipsoidal em LAEA.

    Earth Engine e GIS podem diferir no modelo de superficie: divergencia nao
    equivale automaticamente a erro de calculo.
    """
    erros = []
    for f in feicoes:
        declarada = float(f.propriedades["area_km2"])
        calculada = f.metrico.area / 1e6
        if declarada <= 0:
            continue
        desvio = 100 * (calculada / declarada - 1)
        erros.append((abs(desvio), desvio, f, declarada, calculada))
    erros.sort(key=lambda item: item[0], reverse=True)
    validos = [e[1] for e in erros if e[2].valida_metrica]
    return {
        "metodo": "Area planar em LAEA local/WGS84; valida apos projetar, com reparo condicional em memoria",
        "mediana_desvio_pct_validos": round(statistics.median(validos), 6) if validos else None,
        "desvios_absolutos_acima_1pct": sum(e[0] > 1 for e in erros),
        "desvios_absolutos_acima_5pct": sum(e[0] > 5 for e in erros),
        "amostras_maiores_desvios": [
            dict(amostra(e[2]), geometria_laea_valida=e[2].valida_metrica,
                 area_atributo_km2=round(e[3], 6),
                 area_calculada_km2=round(e[4], 6),
                 desvio_pct=round(e[1], 4)) for e in erros[:12]
        ],
    }


def agrupar(feicoes: list[Feicao]) -> dict[str, list[Feicao]]:
    grupos = defaultdict(list)
    for f in feicoes:
        grupos[f.data].append(f)
    return dict(sorted(grupos.items()))


def relacao_p2_p1(grupos_p1: dict, p2: list[Feicao]) -> dict:
    divergencias = []
    equivalentes = 0
    exatamente_iguais = 0
    maiores_frac = []
    for rm in p2:
        candidatos = [f for f in grupos_p1[rm.data] if f.rank == rm.rank]
        if len(candidatos) != 1:
            divergencias.append(dict(amostra(rm), motivo="Rank ausente ou ambiguo"))
            continue
        p = candidatos[0]
        if p.geometria.__geo_interface__ == rm.geometria.__geo_interface__:
            exatamente_iguais += 1
        uniao = p.metrico.union(rm.metrico)
        diferenca = p.metrico.symmetric_difference(rm.metrico).area
        fracao = diferenca / uniao.area if uniao.area else 0.0
        maiores_frac.append((fracao, rm.data))
        if fracao <= LIMIAR_DIFERENCA_RELATIVA:
            equivalentes += 1
        else:
            divergencias.append(dict(amostra(rm), fracao_diferenca=fracao))
    maiores_frac.sort(reverse=True)
    return {
        "total_p2": len(p2),
        "coincidencia_estrita_coordenadas": exatamente_iguais,
        "equivalentes_topologicamente_apos_projecao": equivalentes,
        "limiar_diferenca_relativa_diagnostica": LIMIAR_DIFERENCA_RELATIVA,
        "maior_diferenca_relativa": maiores_frac[0][0] if maiores_frac else None,
        "divergencias": divergencias[:30],
    }


def sobreposicoes_p1(grupos_p1: dict) -> dict:
    pares = []
    dias = set()
    for dia, feicoes in grupos_p1.items():
        geometrias = [f.metrico for f in feicoes]
        arvore = STRtree(geometrias)
        for i, geom in enumerate(geometrias):
            for j0 in arvore.query(geom):
                j = int(j0)
                if j <= i:
                    continue
                inter = geom.intersection(geometrias[j])
                if inter.area > LIMIAR_INTERSECAO_M2:
                    dias.add(dia)
                    pares.append((dia, feicoes[i].rank, feicoes[j].rank,
                                  inter.area / 1e6))
    pares.sort(key=lambda p: p[3], reverse=True)
    return {
        "limiar_area_diagnostico_m2": LIMIAR_INTERSECAO_M2,
        "pares_com_sobreposicao_de_area": len(pares),
        "datas_com_sobreposicao": len(dias),
        "amostras_maiores_sobreposicoes": [
            {"data": d, "rank_1": r1, "rank_2": r2,
             "area_sobreposicao_km2": round(a, 8)} for d, r1, r2, a in pares[:12]
        ],
    }


def evolucao_temporal(grupos_p1: dict, p2: list[Feicao]) -> dict:
    grupos_p2 = {f.data: f for f in p2}
    datas = sorted(grupos_p1)
    perdas_evento = []
    perdas_rm = []
    fusoes_candidatas = []
    for anterior, atual in zip(datas, datas[1:]):
        componentes_prev = grupos_p1[anterior]
        componentes_atual = grupos_p1[atual]
        uniao_prev = unary_union([f.metrico for f in componentes_prev])
        uniao_atual = unary_union([f.metrico for f in componentes_atual])
        perda_evento = uniao_prev.difference(uniao_atual).area / 1e6
        perda_rm = grupos_p2[anterior].metrico.difference(grupos_p2[atual].metrico).area / 1e6
        if perda_evento * 1e6 > LIMIAR_INTERSECAO_M2:
            perdas_evento.append({"de": anterior, "ate": atual,
                                  "area_nao_contida_km2": round(perda_evento, 7)})
        if perda_rm * 1e6 > LIMIAR_INTERSECAO_M2:
            perdas_rm.append({"de": anterior, "ate": atual,
                              "area_nao_contida_km2": round(perda_rm, 7)})
        arvore_prev = STRtree([f.metrico for f in componentes_prev])
        for novo in componentes_atual:
            anteriores = []
            for i0 in arvore_prev.query(novo.metrico):
                f = componentes_prev[int(i0)]
                inter = novo.metrico.intersection(f.metrico).area
                if inter > LIMIAR_INTERSECAO_M2:
                    anteriores.append(f.rank)
            if len(anteriores) >= 2:
                fusoes_candidatas.append({"de": anterior, "ate": atual,
                                          "rank_atual": novo.rank,
                                          "ranks_anteriores": sorted(anteriores)})
    contador = Counter(x["ate"] for x in fusoes_candidatas)
    fusoes_candidatas.sort(key=lambda item: (-len(item["ranks_anteriores"]), item["ate"]))
    max_perda_evento = max((x["area_nao_contida_km2"] * 1e6
                           for x in perdas_evento), default=0)
    max_perda_rm = max((x["area_nao_contida_km2"] * 1e6
                       for x in perdas_rm), default=0)
    return {
        "area_acumulada_evento_nao_contida_na_observacao_seguinte": perdas_evento,
        "area_acumulada_rm_nao_contida_na_observacao_seguinte": perdas_rm,
        "maior_residuo_evento_m2": round(max_perda_evento, 3),
        "maior_residuo_rm_m2": round(max_perda_rm, 3),
        "intervalos_residuo_evento_acima_100m2": sum(
            x["area_nao_contida_km2"] * 1e6 > LIMIAR_PERDA_RELEVANTE_M2
            for x in perdas_evento),
        "intervalos_residuo_rm_acima_100m2": sum(
            x["area_nao_contida_km2"] * 1e6 > LIMIAR_PERDA_RELEVANTE_M2
            for x in perdas_rm),
        "fusoes_candidatas_por_sobreposicao": len(fusoes_candidatas),
        "datas_com_fusoes_candidatas": dict(sorted(contador.items())),
        "max_componentes_anteriores_convergindo": max(
            (len(x["ranks_anteriores"]) for x in fusoes_candidatas), default=0),
        "exemplos_fusoes_candidatas": fusoes_candidatas[:20],
        "observacao": "Fusao e apenas hipotese por sobreposicao; nao representa comprovacao de fusao fisica do fogo",
    }


def auditar(p1_path: Path, p2_path: Path) -> dict:
    p1 = ler(p1_path)
    p2 = ler(p2_path)
    projecao = preparar_metrico(p1, p2)
    grupos = agrupar(p1)
    return {
        "escopo": "Auditoria exploratoria de geometrias exportadas, nao certificacao cientifica",
        "arquivos": {
            "p1": {"nome": p1_path.name, "sha256": sha256(p1_path.read_bytes()).hexdigest()},
            "p2": {"nome": p2_path.name, "sha256": sha256(p2_path.read_bytes()).hexdigest()},
        },
        "dependencias": {"shapely": shapely.__version__, "pyproj": pyproj.__version__},
        "projecao_diagnostica": projecao,
        "p1": resumo_geometrias(p1),
        "p2": resumo_geometrias(p2),
        "areas_p1": resumo_areas(p1),
        "areas_p2": resumo_areas(p2),
        "p2_versus_p1": relacao_p2_p1(grupos, p2),
        "sobreposicoes_p1": sobreposicoes_p1(grupos),
        "evolucao": evolucao_temporal(grupos, p2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("p1", type=Path)
    parser.add_argument("p2", type=Path)
    parser.add_argument("--saida-json", type=Path,
                        help="Salva relatorio detalhado em JSON, alem do resumo no terminal")
    args = parser.parse_args()
    try:
        dados = auditar(args.p1, args.p2)
        if args.saida_json:
            args.saida_json.parent.mkdir(parents=True, exist_ok=True)
            args.saida_json.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")
        resumo = {
            "p1_invalidos_planos_lonlat": dados["p1"]["invalidas_planas_em_lonlat"],
            "p2_invalidos_planos_lonlat": dados["p2"]["invalidas_planas_em_lonlat"],
            "p1_invalidos_apos_projecao_laea": dados["p1"]["invalidas_apos_projecao_laea"],
            "p2_invalidos_apos_projecao_laea": dados["p2"]["invalidas_apos_projecao_laea"],
            "p2_equivalentes_a_p1": dados["p2_versus_p1"]["equivalentes_topologicamente_apos_projecao"],
            "p1_pares_sobrepostos": dados["sobreposicoes_p1"]["pares_com_sobreposicao_de_area"],
            "intervalos_com_perda_evento": len(dados["evolucao"]["area_acumulada_evento_nao_contida_na_observacao_seguinte"]),
            "intervalos_com_perda_rm": len(dados["evolucao"]["area_acumulada_rm_nao_contida_na_observacao_seguinte"]),
            "maior_residuo_evento_m2": dados["evolucao"]["maior_residuo_evento_m2"],
            "residuos_evento_acima_100m2": dados["evolucao"]["intervalos_residuo_evento_acima_100m2"],
            "fusoes_candidatas": dados["evolucao"]["fusoes_candidatas_por_sobreposicao"],
            "aviso": dados["escopo"],
        }
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError, pyproj.exceptions.ProjError,
            shapely.errors.GEOSException) as exc:
        print(f"FALHA NA AUDITORIA: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
