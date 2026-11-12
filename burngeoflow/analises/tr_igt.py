#!/usr/bin/env python3
"""Fecha a Etapa 4 em Python: TR e diferencas geometricas das regioes P2.

Referencia conceitual: Barbosa & Oliveira (2022), Secao 2, Figura 3.
Reaproveita os modulos Python existentes; preserva os GeoJSON originais.
Nao executa SQL, nao estima frente ativa ou velocidade de propagacao.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from hashlib import sha256
import json
from math import isclose
from pathlib import Path
import sys

import pyproj
from shapely.geometry import shape

from burngeoflow.analises.paisagem import carregar_p1, projetar_patches
from burngeoflow.validacao.topologia_p2 import reconciliar_p2


CAMPOS_COMPARACAO = [
    "id_incendio", "data_anterior", "data_atual", "dias_intervalo", "lacuna_temporal",
    "tr_distancia_centroide_km", "tr_azimute_centroide_graus",
    "tr_avanco_norte_km", "tr_avanco_sul_km", "tr_avanco_leste_km", "tr_avanco_oeste_km",
    "igt_area_nova_km2", "igt_area_reduzida_km2", "igt_area_nova_km2_por_dia",
    "igt_num_componentes_novas", "igt_num_componentes_reducao",
    "igt_azimute_medio_ponderado_graus", "igt_concentracao_direcional",
    "diferenca_angular_tr_igt_graus", "igt_azimute_centroide_area_nova_graus",
    "reducao_maior_que_1m2", "soma_componentes_reducao_erro_m2",
]
CAMPOS_REDUCAO = [
    "id_incendio", "data_anterior", "data_atual", "componente_rank",
    "area_km2", "centroide_longitude", "centroide_latitude",
    "azimute_reducao_graus", "fracao_area_reduzida",
]


def ler_csv_por_transicao(caminho: Path):
    """Indexa CSV por par (data_anterior,data_atual); rejeita repeticoes."""
    with caminho.open(encoding="utf-8", newline="") as arq:
        linhas = list(csv.DictReader(arq))
    indice = {}
    for linha in linhas:
        par = (linha["data_anterior"], linha["data_atual"])
        if par in indice:
            raise ValueError(f"Transicao duplicada em {caminho}: {par}")
        if (date.fromisoformat(par[1])-date.fromisoformat(par[0])).days <= 0:
            raise ValueError(f"Ordem temporal invalida: {par}")
        indice[par] = linha
    return indice


def numero(campo):
    return None if campo in ("", None) else float(campo)


def angulo_minimo(a, b):
    """Diferenca absoluta entre azimutes em [0,180], ou None se indefinidos."""
    if a is None or b is None:
        return None
    return abs((a-b+180) % 360-180)


def partes_poligonais(geometria):
    if geometria.is_empty:
        return []
    if geometria.geom_type == "Polygon":
        return [geometria] if geometria.area > 0 else []
    if geometria.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [p for g in geometria.geoms for p in partes_poligonais(g)]
    raise ValueError(f"Tipo geometrico nao poligonal: {geometria.geom_type}")


def salvar_csv(caminho, campos, linhas):
    with caminho.open("w", encoding="utf-8", newline="") as arq:
        escritor = csv.DictWriter(arq, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)


def direcoes_reducao(g0, g1, inverso, geod, *, evento, dia0, dia1):
    """Barbosa & Oliveira (2022), Fig. 3: R0\\R1 e vetores perda -> centroide R0.

    Nao atribuir movimento fisico a fragmentos subpixel.
    """
    if any(g.is_empty or not g.is_valid or g.area <= 0 for g in (g0, g1)):
        raise ValueError("IGT exige poligonos validos com area positiva")
    perda = g0.difference(g1)
    partes = sorted(partes_poligonais(perda), key=lambda p: (-p.area, p.centroid.x, p.centroid.y))
    lon_ref, lat_ref = inverso.transform(g0.centroid.x, g0.centroid.y)
    saida = []
    for rank, parte in enumerate(partes, 1):
        lon, lat = inverso.transform(parte.centroid.x, parte.centroid.y)
        az, _, dist = geod.inv(lon, lat, lon_ref, lat_ref)
        saida.append({
            "id_incendio": evento, "data_anterior": dia0, "data_atual": dia1,
            "componente_rank": rank, "area_km2": parte.area/1e6,
            "centroide_longitude": lon, "centroide_latitude": lat,
            "azimute_reducao_graus": az % 360 if dist > 1e-6 else None,
            "fracao_area_reduzida": parte.area/perda.area if perda.area else None,
        })
    erro = abs(sum(p.area for p in partes)-perda.area)
    return saida, perda.area/1e6, erro


def comparar_linhas(linha_tr: dict, linha_igt: dict, *, n_reducao: int,
                    soma_reducao_erro_m2: float, az_nova_total=None) -> dict:
    """Combina valores recalculados dos mesmos GeoJSON, sem inferir causalidade."""
    chave = ("id_incendio", "data_anterior", "data_atual", "dias_intervalo")
    for k in chave:
        if str(linha_tr[k]) != str(linha_igt[k]):
            raise ValueError(f"TR e IGT discordam em {k}: {linha_tr[k]} != {linha_igt[k]}")
    area_nova = numero(linha_igt["area_nova_km2"])
    area_perda = numero(linha_igt["area_perdida_km2"])
    dias = int(linha_tr["dias_intervalo"])
    if dias <= 0 or area_nova is None or area_nova < 0 or area_perda is None or area_perda < 0:
        raise ValueError("Area ou periodo invalidos")
    if abs(numero(linha_tr["area_nova_p2_km2"])-area_nova) > 1e-7:
        raise ValueError("Area nova TR/IGT nao confere")
    if abs(numero(linha_tr["area_perdida_p2_km2"])-area_perda) > 1e-7:
        raise ValueError("Area reduzida TR/IGT nao confere")
    a_tr = numero(linha_tr["azimute_centroide_graus"])
    a_igt = numero(linha_igt["azimute_medio_ponderado_graus"])
    return {
        "id_incendio": linha_tr["id_incendio"], "data_anterior": linha_tr["data_anterior"],
        "data_atual": linha_tr["data_atual"], "dias_intervalo": dias,
        "lacuna_temporal": dias > 1,
        "tr_distancia_centroide_km": numero(linha_tr["deslocamento_centroide_km"]),
        "tr_azimute_centroide_graus": a_tr,
        **{f"tr_avanco_{d}_km": numero(linha_tr[f"avanco_{d}_km"])
           for d in ("norte", "sul", "leste", "oeste")},
        "igt_area_nova_km2": area_nova, "igt_area_reduzida_km2": area_perda,
        "igt_area_nova_km2_por_dia": area_nova/dias,
        "igt_num_componentes_novas": int(linha_igt["numero_componentes_incremento"]),
        "igt_num_componentes_reducao": n_reducao,
        "igt_azimute_medio_ponderado_graus": a_igt,
        "igt_concentracao_direcional": numero(linha_igt["concentracao_direcional"]),
        "diferenca_angular_tr_igt_graus": angulo_minimo(a_tr, a_igt),
        "igt_azimute_centroide_area_nova_graus": az_nova_total,
        "reducao_maior_que_1m2": area_perda > 1e-6,
        "soma_componentes_reducao_erro_m2": soma_reducao_erro_m2,
    }



def geometrias_p2_consolidadas(
    p1: Path, p2: Path, *, id_incendio: int, definicao_laea: str,
) -> tuple[dict[str, object], dict]:
    """Reconstitui exatamente a base geométrica usada por TR/IGT.

    O P2 original é conferido rigorosamente contra o P1 pelo mesmo critério
    de reparo auditado, mas os cálculos usam o P1 LAEA canônico. Não altera
    nenhum arquivo fonte e não suprime divergências topológicas.
    """
    patches = carregar_p1(p1)
    projecao, reparos_p1 = projetar_patches(patches)
    if projecao["definicao_laea_proj4"] != definicao_laea:
        raise ValueError("CRS LAEA de TR diverge da reprojeção de P1")
    indice = {(p.data, p.rank): p for p in patches}
    crs = pyproj.CRS.from_proj4(definicao_laea)
    projetor = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True)

    with p2.open(encoding="utf-8") as arq:
        fonte = json.load(arq)
    if fonte.get("type") != "FeatureCollection":
        raise ValueError("P2 deve ser FeatureCollection")
    geometrias = {}
    auditorias = []
    for numero_registro, feicao in enumerate(fonte.get("features", [])):
        try:
            prop = feicao["properties"]
            dia = prop["data"]
            date.fromisoformat(dia)
            rank = int(prop["rank_global"])
            id_lido = int(prop["id_incendio"])
            original = shape(feicao["geometry"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"P2 registro {numero_registro}: campos/geometria inválidos: {exc}"
            ) from exc
        if (id_lido != id_incendio
                or prop["id_incendio"] != id_lido
                or prop["rank_global"] != rank
                or (dia, rank) not in indice
                or dia in geometrias):
            raise ValueError(
                f"P2 registro {numero_registro} ({dia}, rank {rank}): "
                "ID, rank ou data incoerente/duplicada"
            )
        if original.geom_type not in ("Polygon", "MultiPolygon") or original.is_empty:
            raise ValueError(
                f"P2 registro {numero_registro} ({dia}): geometria não poligonal"
            )
        patch = indice[dia, rank]
        _, auditoria = reconciliar_p2(
            original, patch, projetor,
            registro=numero_registro, data=dia, rank=rank,
        )
        auditorias.append(auditoria)
        geometrias[dia] = patch.geometria

    datas_p1 = {p.data for p in patches}
    if set(geometrias) != datas_p1:
        raise ValueError("Datas P1/P2 distintas na consolidação")
    reparos_p2 = [a for a in auditorias if a["reparo_p2_necessario"]]
    return geometrias, {
        "geometrias_p1_reparadas_apos_projecao": reparos_p1,
        "numero_reparos_p2_para_comparacao": len(reparos_p2),
        "reparos_p2_para_comparacao": reparos_p2,
        "maior_diferenca_simetrica_p1_p2_m2": max(
            (a["diferenca_simetrica_m2"] for a in auditorias), default=0,
        ),
        "base_geometrica": "P1 projetado LAEA, reconciliado com P2 por data/rank",
    }


def executar(p1: Path, p2: Path, saida: Path) -> dict:
    """Executa novamente TR/IGT, cruza resultados e documenta a proveniencia."""
    from burngeoflow.analises.regioes_moveis import executar as executar_tr
    from burngeoflow.analises.incrementos import executar as executar_igt
    tr = executar_tr(p1, p2, saida)
    igt = executar_igt(p1, p2, saida)
    if tr["id_incendio"] != igt["id_incendio"] or tr["transicoes"] != igt["transicoes"]:
        raise ValueError("TR e IGT nao concordam em evento/numero de transicoes")
    eid = tr["id_incendio"]
    indice_tr = ler_csv_por_transicao(saida / f"indicadores_regiao_{eid}.csv")
    indice_igt = ler_csv_por_transicao(saida / f"incrementos_temporais_{eid}.csv")
    if set(indice_tr) != set(indice_igt):
        raise ValueError("TR e IGT produziram conjuntos distintos de transicoes")

    definicao = tr["projecao"]["definicao_laea_proj4"]
    crs = pyproj.CRS.from_proj4(definicao)
    inverso = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    geod = pyproj.Geod(ellps="WGS84")
    geoms, auditoria_consolidacao = geometrias_p2_consolidadas(
        p1, p2, id_incendio=eid, definicao_laea=definicao,
    )
    if set(geoms) != {d for par in indice_tr for d in par}:
        raise ValueError("Datas P1/P2 distintas das transicoes")
    for rotina, resumo in (("TR", tr), ("IGT", igt)):
        if (resumo.get("numero_reparos_p2_para_comparacao")
                != auditoria_consolidacao["numero_reparos_p2_para_comparacao"]):
            raise ValueError(
                f"Contagem de reparos P2 divergente entre {rotina} e consolidação"
            )

    comparacoes, perdas = [], []
    for (d0, d1), linha_tr in sorted(indice_tr.items()):
        g0, g1 = geoms[d0], geoms[d1]
        componentes, area_perda, erro = direcoes_reducao(
            g0, g1, inverso, geod, evento=eid, dia0=d0, dia1=d1)
        if not isclose(area_perda, float(indice_igt[(d0,d1)]["area_perdida_km2"]),
                       rel_tol=0, abs_tol=1e-7):
            raise ValueError("Area reduzida reprocessada nao coincide com IGT")
        if erro > 1.0:
            raise ValueError("Soma de componentes de reducao diverge acima de 1 m2")
        nova = g1.difference(g0)
        az_nova = None
        if nova.area > 0:
            a = inverso.transform(g0.centroid.x, g0.centroid.y)
            b = inverso.transform(nova.centroid.x, nova.centroid.y)
            ang, _, distancia = geod.inv(*a, *b)
            if distancia > 1e-6:
                az_nova = ang % 360
        comp = comparar_linhas(linha_tr, indice_igt[(d0,d1)],
                               n_reducao=len(componentes),
                               soma_reducao_erro_m2=erro, az_nova_total=az_nova)
        comparacoes.append(comp)
        perdas.extend(componentes)
    if len(comparacoes) != tr["transicoes"]:
        raise ValueError("Quantidade de transicoes inconsistente")
    salvar_csv(saida / f"comparacao_tr_igt_{eid}.csv", CAMPOS_COMPARACAO, comparacoes)
    salvar_csv(saida / f"componentes_reducao_{eid}.csv", CAMPOS_REDUCAO, perdas)
    angulos = [r["diferenca_angular_tr_igt_graus"] for r in comparacoes
               if r["diferenca_angular_tr_igt_graus"] is not None]
    resumo = {
        "id_incendio": eid, "metodologia": "TR_IGT_barbosa_oliveira_2022_adaptacao_P2",
        "fonte": "Barbosa e Oliveira (2022), secao 2, figura 3; Oliveira (2024)",
        "status": "confronto_matematico_Python; sem_validacao_fisica_frente_fogo",
        "datas": tr["datas"], "transicoes": len(comparacoes),
        "correspondencia_p1_p2": f'{tr["ranks_rastreamento_conferem"]}/{tr["datas"]}',
        "componentes_area_acrescida": igt["componentes_incremento"],
        "componentes_area_reduzida": len(perdas),
        "transicoes_reducao_maior_1m2": sum(r["reducao_maior_que_1m2"] for r in comparacoes),
        "area_nova_total_km2": igt["area_nova_total_km2"],
        "area_reduzida_total_km2": igt["area_perdida_total_km2"],
        "lacunas": [r["data_atual"] for r in comparacoes if r["lacuna_temporal"]],
        "transicoes_direcoes_comparaveis": len(angulos),
        "transicoes_direcao_IGT_indefinida": len(comparacoes)-len(angulos),
        "diferenca_angular_tr_igt_mediana_graus": sorted(angulos)[len(angulos)//2] if angulos else None,
        "auditoria_geometrica_consolidacao": auditoria_consolidacao,
        "hash_sha256_p1": sha256(p1.read_bytes()).hexdigest(),
        "hash_sha256_p2": sha256(p2.read_bytes()).hexdigest(),
        "sql": "arquivado_como_referencia; nao_executado; nao_e_dependencia",
        "observacao": "Deslocamento dos descritores e incremento de area detectada nao sao velocidade da frente do fogo.",
    }
    (saida / f"resumo_consolidado_tr_igt_{eid}.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return resumo


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("p1", type=Path)
    ap.add_argument("p2", type=Path)
    ap.add_argument("--saida", type=Path, required=True)
    args = ap.parse_args()
    try:
        print(json.dumps(executar(args.p1,args.p2,args.saida),ensure_ascii=False,indent=2))
    except (OSError, ValueError, KeyError, pyproj.ProjError) as exc:
        print(f"FALHA: {exc}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
