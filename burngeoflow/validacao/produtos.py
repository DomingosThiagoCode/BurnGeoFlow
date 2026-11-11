#!/usr/bin/env python3
"""Confere a consistência numérica de P1/P2 exportados do GEE.

Não realiza operações topológicas, reprojeções ou validação científica.
Usa somente a biblioteca padrão do Python 3.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, timedelta
import json
from math import isclose, isfinite
from pathlib import Path
import sys


def exigir(condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise ValueError(mensagem)


def numero(valor: object, campo: str) -> float:
    exigir(isinstance(valor, (int, float)) and not isinstance(valor, bool),
           f"O campo {campo} precisa ser numérico: {valor!r}")
    valor_float = float(valor)
    exigir(isfinite(valor_float), f"O campo {campo} não é finito")
    return valor_float


def inteiro(valor: object, campo: str) -> int:
    valor_float = numero(valor, campo)
    exigir(valor_float.is_integer(), f"O campo {campo} não é inteiro: {valor}")
    return int(valor_float)


def proximo(a: float, b: float) -> bool:
    return isclose(a, b, rel_tol=1e-8, abs_tol=1e-6)


def carregar(caminho: Path, obrigatorios: set[str]) -> list[dict]:
    with caminho.open(encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    exigir(dados.get("type") == "FeatureCollection",
           f"{caminho}: GeoJSON não é FeatureCollection")
    feicoes = dados.get("features")
    exigir(isinstance(feicoes, list) and feicoes,
           f"{caminho}: coleção vazia ou sem lista de feições")
    for indice, feicao in enumerate(feicoes):
        exigir(feicao.get("type") == "Feature",
               f"{caminho}: registro {indice} não é Feature")
        propriedades = feicao.get("properties")
        exigir(isinstance(propriedades, dict),
               f"{caminho}: registro {indice} sem propriedades")
        faltantes = obrigatorios - propriedades.keys()
        exigir(not faltantes,
               f"{caminho}: registro {indice} sem campos {sorted(faltantes)}")
        geometria = feicao.get("geometry")
        exigir(isinstance(geometria, dict) and
               geometria.get("type") in ("Polygon", "MultiPolygon") and
               bool(geometria.get("coordinates")),
               f"{caminho}: registro {indice} sem geometria poligonal")
        try:
            date.fromisoformat(propriedades["data"])
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Data inválida no registro {indice}: "
                             f"{propriedades['data']!r}") from exc
    return feicoes


def verificar(p1_path: Path, p2_path: Path) -> dict:
    comuns = {"data", "id_incendio", "rank", "area_km2",
              "numero_componentes", "area_total_km2"}
    p1 = carregar(p1_path, comuns)
    p2 = carregar(p2_path, comuns | {"rank_global", "delta_area_km2",
                                      "delta_area_total_km2"})

    grupos_p1 = defaultdict(list)
    ids = set()
    for feicao in p1:
        prop = feicao["properties"]
        grupos_p1[prop["data"]].append(prop)
        ids.add(inteiro(prop["id_incendio"], "id_incendio"))
    exigir(len(ids) == 1, f"P1 contém múltiplos IDs: {sorted(ids)}")

    areas_p1 = {}
    indices_p1 = {}
    for dia, props in grupos_p1.items():
        n = len(props)
        ranks = [inteiro(p["rank"], "rank") for p in props]
        exigir(sorted(ranks) == list(range(1, n + 1)),
               f"{dia}: ranks do P1 duplicados ou incompletos")
        areas = [numero(p["area_km2"], "area_km2") for p in props]
        exigir(all(area > 0 for area in areas),
               f"{dia}: área nula ou negativa em P1")
        total = sum(areas)
        for prop in props:
            exigir(inteiro(prop["numero_componentes"], "numero_componentes") == n,
                   f"{dia}: número de componentes inconsistente")
            exigir(proximo(numero(prop["area_total_km2"], "area_total_km2"), total),
                   f"{dia}: área total não coincide com a soma do P1")
            indices_p1[(dia, inteiro(prop["rank"], "rank"))] = prop
        exigir(proximo(numero(next(p for p in props if inteiro(p["rank"], "rank") == 1)["area_km2"], "area_km2"), max(areas)),
               f"{dia}: rank 1 não possui a maior área")
        areas_p1[dia] = total

    grupos_p2 = defaultdict(list)
    for feicao in p2:
        prop = feicao["properties"]
        grupos_p2[prop["data"]].append(prop)
        exigir(inteiro(prop["id_incendio"], "id_incendio") in ids,
               f"{prop['data']}: ID do P2 diverge do P1")
    exigir(set(grupos_p1) == set(grupos_p2),
           "P1 e P2 não possuem as mesmas datas")
    exigir(all(len(v) == 1 for v in grupos_p2.values()),
           "P2 precisa ter uma única região móvel por data")

    dias = sorted(grupos_p1)
    lacunas = []
    for indice, dia in enumerate(dias):
        prop = grupos_p2[dia][0]
        rank = inteiro(prop["rank_global"], "rank_global")
        exigir(inteiro(prop["rank"], "rank") == rank,
               f"{dia}: rank e rank_global divergentes no P2")
        candidato = indices_p1.get((dia, rank))
        exigir(candidato is not None, f"{dia}: RM não encontrada no P1")
        area_rm = numero(prop["area_km2"], "area_km2")
        exigir(proximo(area_rm, numero(candidato["area_km2"], "area_km2")),
               f"{dia}: área da RM diverge do componente correspondente")
        exigir(proximo(numero(prop["area_total_km2"], "area_total_km2"), areas_p1[dia]),
               f"{dia}: área acumulada de P1/P2 divergente")
        exigir(inteiro(prop["numero_componentes"], "numero_componentes") == len(grupos_p1[dia]),
               f"{dia}: quantidade de componentes de P1/P2 divergente")

        if indice:
            anterior = dias[indice - 1]
            area_rm_anterior = numero(grupos_p2[anterior][0]["area_km2"], "area_km2")
            delta_rm = area_rm - area_rm_anterior
            delta_total = areas_p1[dia] - areas_p1[anterior]
            exigir(delta_rm >= -1e-6 and delta_total >= -1e-6,
                   f"{dia}: área acumulada diminuiu")
            intervalo = (date.fromisoformat(dia) - date.fromisoformat(anterior)).days
            exigir(intervalo > 0, f"{dia}: ordem cronológica inválida")
            if intervalo > 1:
                lacunas.append({"de": anterior, "ate": dia, "dias": intervalo})
        else:
            delta_rm = 0.0
            delta_total = 0.0
        exigir(proximo(numero(prop["delta_area_km2"], "delta_area_km2"), delta_rm),
               f"{dia}: delta_area_km2 inconsistente")
        exigir(proximo(numero(prop["delta_area_total_km2"], "delta_area_total_km2"), delta_total),
               f"{dia}: delta_area_total_km2 inconsistente")

    ultima = dias[-1]
    return {
        "id_incendio": next(iter(ids)),
        "datas": len(dias),
        "inicio": dias[0],
        "fim": ultima,
        "registros_p1": len(p1),
        "registros_p2": len(p2),
        "max_componentes_dia": max(len(g) for g in grupos_p1.values()),
        "area_total_final_km2": round(areas_p1[ultima], 4),
        "area_rm_final_km2": round(numero(grupos_p2[ultima][0]["area_km2"], "area_km2"), 4),
        "lacunas_temporais": lacunas,
        "aviso": "Validação estrutural e numérica, não topológica ou científica",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("p1", type=Path, help="GeoJSON P1 exportado pelo GEE")
    parser.add_argument("p2", type=Path, help="GeoJSON P2 exportado pelo GEE")
    args = parser.parse_args()
    try:
        resultado = verificar(args.p1, args.p2)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FALHA: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
