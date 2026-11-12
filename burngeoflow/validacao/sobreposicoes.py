"""Diagnostico P1: sobreposicoes por data e por par de patches, sem alteracoes.

Opera no mesmo CRS LAEA e com os mesmos reparos condicionais da Etapa 5.
Distingue area em duplicidade na soma/união da soma das interseções dos pares
(que não coincide necessariamente com a primeira se houver interseção tripla).
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

import shapely
from shapely.validation import explain_validity

from burngeoflow.analises.paisagem import carregar_p1, projetar_patches


def diagnosticar_grupo(patches: list, *, top_n: int = 15) -> dict:
    """Patches já projetados. Retorna ranks, sobreposições e reparos."""
    if not patches:
        raise ValueError("Grupo P1 vazio")
    if top_n < 1:
        raise ValueError("top_n precisa ser positivo")
    geoms = [p.geometria for p in patches]
    if any(not g.is_valid or g.is_empty or g.area <= 0 for g in geoms):
        raise ValueError("Diagnostico requer geometrias P1 LAEA validas")
    arvore = shapely.STRtree(geoms)
    pares = []
    for i, geom in enumerate(geoms):
        for j in arvore.query(geom, predicate="intersects"):
            j = int(j)
            if j <= i:
                continue
            area = geom.intersection(geoms[j]).area
            if area <= 0:
                continue
            a, b = patches[i], patches[j]
            pares.append({
                "rank_a": a.rank,
                "rank_b": b.rank,
                "intersecao_m2": area,
                "fracao_area_menor_pct": 100 * area / min(geom.area, geoms[j].area),
                "area_a_m2": geom.area,
                "area_b_m2": geoms[j].area,
                "a_reparado_apos_projecao": a.reparado_apos_projecao,
                "b_reparado_apos_projecao": b.reparado_apos_projecao,
            })
    pares.sort(key=lambda p: (-p["intersecao_m2"], p["rank_a"], p["rank_b"]))
    area_somada = sum(g.area for g in geoms)
    area_uniao = shapely.union_all(geoms).area
    return {
        "data": patches[0].data,
        "numero_patches": len(patches),
        "numero_patches_reparados": sum(p.reparado_apos_projecao for p in patches),
        "numero_pares_sobrepostos": len(pares),
        "excesso_area_somada_sobre_uniao_m2": max(0.0, area_somada - area_uniao),
        "area_somada_patches_m2": area_somada,
        "area_uniao_m2": area_uniao,
        "soma_intersecoes_pares_m2": sum(p["intersecao_m2"] for p in pares),
        "maior_intersecao_par_m2": pares[0]["intersecao_m2"] if pares else 0.0,
        "todos_pares_acima_1_m2": sum(p["intersecao_m2"] > 1.0 for p in pares),
        "pares_mais_relevantes": pares[:top_n],
        "pares_omitidos_no_resumo": max(0, len(pares) - top_n),
    }


def diagnosticar_arquivo(p1: Path, *, data: str | None = None,
                        top_n: int = 15) -> dict:
    """Não modifica o P1, inclusive quando os patches exigiram make_valid."""
    patches = carregar_p1(p1)
    fonte = {
        (p.data, p.rank): {
            "validade_wgs84": bool(p.geometria.is_valid),
            "motivo_invalidade_wgs84": (
                None if p.geometria.is_valid else explain_validity(p.geometria)
            ),
        }
        for p in patches
    }
    crs, reparos = projetar_patches(patches)
    grupos = defaultdict(list)
    for p in patches:
        grupos[p.data].append(p)
    if data is not None and data not in grupos:
        raise ValueError(f"Data inexistente no P1: {data}")
    escolhidos = [data] if data else sorted(grupos)
    dias = []
    for dia in escolhidos:
        resultado = diagnosticar_grupo(grupos[dia], top_n=top_n)
        for par in resultado["pares_mais_relevantes"]:
            par["p1_a_original"] = fonte[(dia, par["rank_a"])]
            par["p1_b_original"] = fonte[(dia, par["rank_b"])]
        dias.append(resultado)
    return {
        "produto": str(p1),
        "metodo": "STRtree/intersecao por par no mesmo LAEA da Etapa 5",
        "criterio_etapa5_m2": 1.0,
        "nao_altera_origem": True,
        "crs_laea": crs["definicao_laea_proj4"],
        "total_patches_lidos": len(patches),
        "total_reparados_laea": reparos,
        "datas_avaliadas": len(dias),
        "datas_que_excedem_1m2": [
            x["data"] for x in dias if x["excesso_area_somada_sobre_uniao_m2"] > 1.0
        ],
        "datas": dias,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--data", help="Data YYYY-MM-DD; omita para auditar todas")
    ap.add_argument("--p1", type=Path, help="GeoJSON P1; padrão: execucoes/<ID>/dados/...")
    ap.add_argument("--saida", type=Path, help="Caminho JSON do diagnóstico")
    ap.add_argument("--top-n", type=int, default=15)
    args = ap.parse_args(argv)
    raiz = Path(__file__).resolve().parents[2] / "execucoes" / str(args.id)
    p1 = args.p1 or (
        raiz / "dados" / f"estudo_caso_{args.id}"
        / f"P1_componentes_{args.id}.geojson"
    )
    destino = args.saida or (
        raiz / "resultados" / "etapa5"
        / f"diagnostico_sobreposicoes_p1_{args.id}.json"
    )
    try:
        relatorio = diagnosticar_arquivo(p1, data=args.data, top_n=args.top_n)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(relatorio, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print("[DIAGNOSTICO] Sobreposicoes P1, sem alterar geometrias.")
        print(f"[DIAGNOSTICO] Arquivo: {destino}")
        for dia in relatorio["datas"]:
            print(
                f"[{dia['data']}] patches={dia['numero_patches']} "
                f"reparados={dia['numero_patches_reparados']} "
                f"pares={dia['numero_pares_sobrepostos']} "
                f"excesso_soma_uniao={dia['excesso_area_somada_sobre_uniao_m2']:.6f} m2"
            )
            for par in dia["pares_mais_relevantes"]:
                print(
                    f"  ranks {par['rank_a']}/{par['rank_b']}: "
                    f"intersecao={par['intersecao_m2']:.6f} m2 "
                    f"({par['fracao_area_menor_pct']:.6f}% do menor); "
                    f"reparos={par['a_reparado_apos_projecao']}/"
                    f"{par['b_reparado_apos_projecao']}"
                )
        return 0
    except (ValueError, OSError, KeyError, shapely.GEOSException) as exc:
        print(f"[ERRO DIAGNOSTICO] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
