"""Diagnostico P1: sobreposicoes por data e por par de patches, sem alteracoes.

Opera no mesmo CRS LAEA e com os mesmos reparos condicionais da Etapa 5.
Distingue area em duplicidade na soma/união da soma das interseções dos pares
(que não coincide necessariamente com a primeira se houver interseção tripla).
"""
from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import pyproj
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




def _intersecao_valida(a, b, *, conversor=None) -> dict:
    """Audita o contato no CRS de entrada antes de qualquer transformação.

    Em WGS84, área positiva em graus² prova sobreposição areal (não mede
    área métrica). O resultado da projeção só serve para a medida em m²;
    sua eventual invalidade não apaga a evidência topológica original.
    Não realizamos overlay sobre geometrias de entrada inválidas.
    """
    if not a.is_valid or not b.is_valid:
        return {"area_m2": None, "situacao": "geometria_invalida"}
    try:
        inter = a.intersection(b)
        if not inter.is_valid:
            return {
                "area_m2": None, "situacao": "intersecao_original_invalida",
            }
        # Evidências em CRS geográfico só existem quando esse é o CRS
        # da entrada. Não interpretar graus² como área métrica.
        evidencia = (
            {
                "area_intersecao_original_graus2": float(inter.area),
                "sobreposicao_areal_no_original": bool(inter.area > 0),
                "intersecao_original_valida": True,
            }
            if conversor is not None else {}
        )
        if conversor is not None and not inter.is_empty:
            inter = shapely.transform(
                inter, conversor.transform, interleaved=False,
            )
        if not inter.is_valid:
            return {
                **evidencia,
                "area_m2": None,
                "situacao": "intersecao_projetada_invalida",
            }
        return {
            **evidencia,
            "area_m2": float(inter.area),
            "situacao": "calculada",
        }
    except (shapely.GEOSException, ValueError, pyproj.exceptions.ProjError) as exc:
        return {
            "area_m2": None,
            "situacao": "erro_na_operacao_topologica",
            "erro": f"{type(exc).__name__}: {exc}",
        }


def _classificar_origem(original, projetada, corrigida) -> str:
    # Prova topológica independente da área métrica projetada.
    # Um interseção em WGS84 com área positiva já estava no GeoJSON.
    if original.get("sobreposicao_areal_no_original") is True:
        return "JA_EXISTIA_NO_GEOJSON_ORIGINAL"
    if original["area_m2"] is None and original.get(
        "sobreposicao_areal_no_original"
    ) is not False:
        return "INDETERMINADO_ORIGINAL_INVALIDO_OU_OVERLAY_IMPOSSIVEL"
    if original["area_m2"] is not None and original["area_m2"] > 0:
        return "JA_EXISTIA_NO_GEOJSON_ORIGINAL"
    if corrigida["area_m2"] is None:
        return "INDETERMINADO_APOS_REPARO"
    if corrigida["area_m2"] == 0:
        return "SEM_SOBREPOSICAO_DE_AREA"
    if projetada["area_m2"] is None:
        return "SURGIU_NA_PROJECAO_OU_REPARO_SEM_SEPARACAO_CONFIAVEL"
    if projetada["area_m2"] > 0:
        return "SURGIU_ANTES_DO_REPARO_NA_PROJECAO"
    return "SURGIU_NO_REPARO"


def verificar_origem(p1_path: Path, *, data: str, principal: int = 1,
                    outros: tuple[int, ...] = (10, 16, 18)) -> dict:
    """Compara 3 estados dos mesmos ranks; nao altera fontes, nao chama GEE."""
    date.fromisoformat(data)
    if principal < 1 or not outros or any(r < 1 or r == principal for r in outros):
        raise ValueError("Ranks precisam ser positivos e diferentes do principal")
    if len(set(outros)) != len(outros):
        raise ValueError("Ranks repetidos na comparacao")
    patches = carregar_p1(p1_path)
    indice = {p.rank: p for p in patches if p.data == data}
    exigidos = {principal, *outros}
    ausentes = exigidos - set(indice)
    if ausentes:
        raise ValueError(f"{data}: ranks inexistentes {sorted(ausentes)}")
    originais = {r: indice[r].geometria for r in exigidos}
    # Fundamental: projetar_patches usa o centro da extensao de TODAS as
    # datas do incendio, nao apenas dos quatro patches selecionados.
    crs, reparados = projetar_patches(patches)
    tx = pyproj.Transformer.from_crs(
        "EPSG:4326",
        pyproj.CRS.from_proj4(crs["definicao_laea_proj4"]),
        always_xy=True,
    )
    projetados = {
        r: shapely.transform(g, tx.transform, interleaved=False)
        for r, g in originais.items()
    }
    corrigidos = {r: indice[r].geometria for r in exigidos}
    estados = {}
    for r in sorted(exigidos):
        a, b, c = originais[r], projetados[r], corrigidos[r]
        estados[str(r)] = {
            "original_valida_wgs84": bool(a.is_valid),
            "original_motivo_invalidade": (
                None if a.is_valid else explain_validity(a)
            ),
            "projetada_valida_antes_make_valid": bool(b.is_valid),
            "projetada_motivo_invalidade": (
                None if b.is_valid else explain_validity(b)
            ),
            "corrigida_valida": bool(c.is_valid),
            "reparo_aplicado": bool(indice[r].reparado_apos_projecao),
        }
    pares = []
    for outro in outros:
        origem = _intersecao_valida(
            originais[principal], originais[outro], conversor=tx,
        )
        pre = _intersecao_valida(projetados[principal], projetados[outro])
        pos = _intersecao_valida(corrigidos[principal], corrigidos[outro])
        pares.append({
            "rank_principal": principal, "rank_outro": outro,
            "original_wgs84_intersecao_convertida_laea": origem,
            "projetada_laea_antes_reparo": pre,
            "projetada_laea_apos_reparo": pos,
            "classificacao": _classificar_origem(origem, pre, pos),
        })
    return {
        "data": data,
        "id_incendio": indice[principal].incendio,
        "arquivo": str(p1_path.resolve()),
        "sha256_p1": sha256(p1_path.read_bytes()).hexdigest(),
        "projecao_laea": crs["definicao_laea_proj4"],
        "reparos_totais_evento": reparados,
        "ranks": estados,
        "pares": pares,
        "nota_metodologica": (
            "Area original calculada pela intersecao em WGS84 e convertida "
            "para a LAEA local. Operacoes sobre geometria invalida nao sao "
            "aceitas. Se apos a projecao a geometria ainda for invalida, "
            "nao e possivel separar confiavelmente efeito da projecao e "
            "efeito de make_valid. Nao equivale a validacao externa."
        ),
        "arquivos_originais_modificados": False,
    }

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--data", help="Data YYYY-MM-DD; omita para auditar todas")
    ap.add_argument("--p1", type=Path, help="GeoJSON P1; padrão: execucoes/<ID>/dados/...")
    ap.add_argument("--saida", type=Path, help="Caminho JSON do diagnóstico")
    ap.add_argument("--top-n", type=int, default=15)
    ap.add_argument("--verificar-origem", action="store_true",
                    help="Compara antes/após LAEA e make_valid, sem alterar P1")
    ap.add_argument("--principal", type=int, default=1)
    ap.add_argument("--outros", type=int, nargs="+", default=[10, 16, 18])
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
        if args.verificar_origem:
            if not args.data:
                raise ValueError("--verificar-origem exige --data")
            relatorio = verificar_origem(
                p1, data=args.data, principal=args.principal,
                outros=tuple(args.outros),
            )
            destino = args.saida or (
                raiz / "resultados" / "etapa5"
                / f"verificacao_origem_p1_{args.id}_{args.data}.json"
            )
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(
                json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"[VERIFICACAO ORIGEM] {args.data} | Relatorio: {destino}")
            for rank, estado in relatorio["ranks"].items():
                print(
                    f"  rank {rank}: original_valido="
                    f"{estado['original_valida_wgs84']}, "
                    f"LAEA_pre_reparo_valido="
                    f"{estado['projetada_valida_antes_make_valid']}, "
                    f"reparo={estado['reparo_aplicado']}"
                )
            for par in relatorio["pares"]:
                def fmt(etapa):
                    valor = etapa["area_m2"]
                    return ("INDETERMINADO" if valor is None
                            else f"{valor:.9f} m2")
                print(
                    f"  ranks {par['rank_principal']}/{par['rank_outro']}: "
                    f"original={fmt(par['original_wgs84_intersecao_convertida_laea'])}; "
                    f"LAEA_sem_reparo={fmt(par['projetada_laea_antes_reparo'])}; "
                    f"LAEA_final={fmt(par['projetada_laea_apos_reparo'])}"
                )
                print(f"    => {par['classificacao']}")
            return 0
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
