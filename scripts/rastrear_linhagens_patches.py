#!/usr/bin/env python3
"""Etapa 3: rastreia relacionamentos geometricos entre patches P1 consecutivos.

Os patches representam AREA QUEIMADA ACUMULADA, nao frentes ativas ou
ignicoes. So intersecoes com area acima do limiar conectam datas distintas;
contatos apenas pontuais/lineares nao estabelecem continuidade temporal.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import sys

import pyproj
import shapely

from calcular_metricas_paisagem import (
    Patch, carregar_p1, projetar_patches, salvar_csv,
)


CAMPOS_LINHAGENS = [
    "id_incendio", "data", "rank", "id_patch_data", "id_linhagem",
    "data_inicio_linhagem", "tipo_entrada", "evento_entrada",
    "numero_antecessores", "ranks_antecessores",
    "linhagens_antecessoras", "area_laea_km2",
    "area_herdada_anterior_pct", "numero_sucessores",
    "ranks_sucessores", "tipo_saida",
]

CAMPOS_VINCULOS = [
    "id_incendio", "data_anterior", "data_atual", "dias_intervalo",
    "rank_anterior", "rank_atual", "id_patch_anterior", "id_patch_atual",
    "linhagem_anterior", "linhagem_atual", "area_intersecao_km2",
    "porcentagem_patch_anterior", "porcentagem_patch_atual", "id_evento",
    "tipo_evento",
]

CAMPOS_EVENTOS = [
    "id_incendio", "id_evento", "data_anterior", "data_atual",
    "dias_intervalo", "tipo_evento", "numero_patches_anteriores",
    "numero_patches_atuais", "ranks_anteriores", "ranks_atuais",
    "area_anteriores_km2", "area_atuais_km2",
    "diferenca_areas_km2",
]

CAMPOS_TRANSICOES = [
    "id_incendio", "data_anterior", "data_atual", "dias_intervalo",
    "patches_anteriores", "patches_atuais", "vinculos_por_area",
    "eventos_continuacao", "eventos_convergencia",
    "eventos_divergencia", "eventos_reorganizacao",
    "eventos_surgimento_sem_sobreposicao", "eventos_sem_sucessor",
    "pares_contato_somente_pontual", "pares_contato_somente_linear",
    "porcentagem_area_anterior_vinculada",
    "porcentagem_area_atual_com_antecessor",
    "area_acumulada_anterior_km2", "area_acumulada_atual_km2",
    "crescimento_liquido_km2",
]


def id_patch(p: Patch) -> str:
    return f"{p.data}_r{p.rank:03d}"


def agrupar_patches(patches: list[Patch]) -> dict[str, list[Patch]]:
    if not patches or any(p.area_m2 <= 0 or not p.geometria.is_valid
                          for p in patches):
        raise ValueError("Patches precisam estar projetados e validos em LAEA")
    por_data: dict[str, list[Patch]] = defaultdict(list)
    for p in patches:
        por_data[p.data].append(p)
    for dia, grupo in por_data.items():
        grupo.sort(key=lambda p: p.rank)
        if [p.rank for p in grupo] != list(range(1, len(grupo) + 1)):
            raise ValueError(f"{dia}: ranks ausentes ou duplicados")
    return dict(sorted(por_data.items()))


def vincular_por_area(
    anteriores: list[Patch], atuais: list[Patch], area_minima_m2: float = 1.0
) -> tuple[list[tuple[int, int, float]], dict[int, list[int]],
           dict[int, list[int]], dict[str, int]]:
    """Retorna arestas (rank_prev, rank_atual, intersecao_m2).

    `area_minima_m2` e um limiar numerico *absoluto*, nao um criterio para
    afirmar fusao fisica. Sobreposicao igual ao limiar nao forma vinculo.
    """
    if not isfinite(area_minima_m2) or area_minima_m2 < 0:
        raise ValueError("area_minima_m2 deve ser finita e >= 0")
    filhos = {p.rank: [] for p in anteriores}
    pais = {p.rank: [] for p in atuais}
    arestas: list[tuple[int, int, float]] = []
    contatos = {"pontual": 0, "linear": 0}
    arvore = shapely.STRtree([p.geometria for p in anteriores])
    for novo in atuais:
        for i in arvore.query(novo.geometria, predicate="intersects"):
            antigo = anteriores[int(i)]
            inter = antigo.geometria.intersection(novo.geometria)
            area = inter.area
            if area > area_minima_m2:
                arestas.append((antigo.rank, novo.rank, area))
                filhos[antigo.rank].append(novo.rank)
                pais[novo.rank].append(antigo.rank)
            elif area == 0 and antigo.geometria.touches(novo.geometria):
                contatos["linear" if inter.length > 1e-6 else "pontual"] += 1
    arestas.sort(key=lambda x: (x[0], x[1]))
    for lista in (*pais.values(), *filhos.values()):
        lista.sort()
    # Se duas feicoes de uma mesma data se sobrepoem de verdade, somar
    # intersecoes duplicaria a area herdada. A divisao em componentes P1
    # deve impedir isso; resultados incoerentes provocam erro explicito.
    por_ant = defaultdict(float)
    por_nov = defaultdict(float)
    for ra, rn, area in arestas:
        por_ant[ra] += area
        por_nov[rn] += area
    for grupo, somas, lado in ((anteriores, por_ant, "anterior"),
                              (atuais, por_nov, "atual")):
        for p in grupo:
            if somas[p.rank] > p.area_m2 + max(1.0, p.area_m2 * 1e-8):
                raise ValueError(
                    f"Patch {lado} {p.data} rank {p.rank}: soma das "
                    "intersecoes maior que a propria area; revisar "
                    "sobreposicoes em P1"
                )
    return arestas, pais, filhos, contatos


def eventos_bipartidos(
    anteriores: list[Patch], atuais: list[Patch],
    pais: dict[int, list[int]], filhos: dict[int, list[int]],
) -> list[tuple[str, list[int], list[int]]]:
    """Componentes do grafo bipartido entre duas datas observadas.

    Casos N->1, 1->N e N->M sao configuracoes geometricas, nao causas.
    """
    visitados_a: set[int] = set()
    visitados_n: set[int] = set()
    grupos = []
    for p in anteriores:
        if p.rank in visitados_a:
            continue
        fila = [("ant", p.rank)]
        ant, nov = set(), set()
        while fila:
            lado, rank = fila.pop()
            if lado == "ant":
                if rank in visitados_a:
                    continue
                visitados_a.add(rank)
                ant.add(rank)
                fila.extend(("nov", i) for i in filhos[rank])
            else:
                if rank in visitados_n:
                    continue
                visitados_n.add(rank)
                nov.add(rank)
                fila.extend(("ant", i) for i in pais[rank])
        grupos.append((sorted(ant), sorted(nov)))
    for p in atuais:
        if p.rank not in visitados_n:
            visitados_n.add(p.rank)
            grupos.append(([], [p.rank]))
    classificados = []
    for ant, nov in grupos:
        if not nov:
            tipo = "sem_sucessor"
        elif not ant:
            tipo = "surgimento_sem_sobreposicao"
        elif len(ant) == len(nov) == 1:
            tipo = "continuacao"
        elif len(ant) > 1 and len(nov) == 1:
            tipo = "convergencia"
        elif len(ant) == 1 and len(nov) > 1:
            tipo = "divergencia"
        else:
            tipo = "reorganizacao"
        classificados.append((tipo, ant, nov))
    return classificados


def analisar_linhagens(
    patches: list[Patch], area_minima_m2: float = 1.0
) -> tuple[list[dict], list[dict], list[dict], list[dict], dict]:
    if not isfinite(area_minima_m2) or area_minima_m2 < 0:
        raise ValueError("area_minima_m2 deve ser finita e >= 0")
    por_data = agrupar_patches(patches)
    datas = list(por_data)
    incendio = patches[0].incendio
    if any(p.incendio != incendio for p in patches):
        raise ValueError("Multiplos IDs de incendio nos patches")
    registros: dict[tuple[str, int], dict] = {}
    vinculos: list[dict] = []
    eventos: list[dict] = []
    transicoes: list[dict] = []
    linhagens: dict[tuple[str, int], str] = {}
    inicio_linhagem = {}
    proximo_id = 0

    def nova_linhagem(dia: str) -> str:
        nonlocal proximo_id
        proximo_id += 1
        identificador = f"L{proximo_id:06d}"
        inicio_linhagem[identificador] = dia
        return identificador

    for p in por_data[datas[0]]:
        chave = (p.data, p.rank)
        identidade = nova_linhagem(p.data)
        linhagens[chave] = identidade
        registros[chave] = {
            "id_incendio": incendio, "data": p.data, "rank": p.rank,
            "id_patch_data": id_patch(p), "id_linhagem": identidade,
            "data_inicio_linhagem": p.data,
            "tipo_entrada": "linha_de_base", "evento_entrada": None,
            "numero_antecessores": None, "ranks_antecessores": "",
            "linhagens_antecessoras": "", "area_laea_km2": p.area_m2 / 1e6,
            "area_herdada_anterior_pct": None,
            "numero_sucessores": None, "ranks_sucessores": "",
            "tipo_saida": None,
        }

    for dia_anterior, dia_atual in zip(datas, datas[1:]):
        ant, nov = por_data[dia_anterior], por_data[dia_atual]
        dias = (date.fromisoformat(dia_atual) - date.fromisoformat(dia_anterior)).days
        if dias <= 0:
            raise ValueError("Datas fora de ordem")
        arestas, pais, filhos, contatos = vincular_por_area(
            ant, nov, area_minima_m2
        )
        grupos = eventos_bipartidos(ant, nov, pais, filhos)
        por_rank_ant = {p.rank: p for p in ant}
        por_rank_nov = {p.rank: p for p in nov}
        mapa_eventos = {}
        contagens = Counter()
        for sequencia, (tipo, ranks_ant, ranks_nov) in enumerate(grupos, 1):
            evento_id = (f"{dia_anterior.replace('-', '')}_"
                         f"{dia_atual.replace('-', '')}_E{sequencia:03d}")
            for rank in ranks_nov:
                mapa_eventos[rank] = (evento_id, tipo)
            a_ant = sum(por_rank_ant[i].area_m2 for i in ranks_ant) / 1e6
            a_nov = sum(por_rank_nov[i].area_m2 for i in ranks_nov) / 1e6
            eventos.append({
                "id_incendio": incendio, "id_evento": evento_id,
                "data_anterior": dia_anterior, "data_atual": dia_atual,
                "dias_intervalo": dias, "tipo_evento": tipo,
                "numero_patches_anteriores": len(ranks_ant),
                "numero_patches_atuais": len(ranks_nov),
                "ranks_anteriores": ";".join(map(str, ranks_ant)),
                "ranks_atuais": ";".join(map(str, ranks_nov)),
                "area_anteriores_km2": a_ant, "area_atuais_km2": a_nov,
                "diferenca_areas_km2": a_nov - a_ant,
            })
            contagens[tipo] += 1

        for p in ant:
            chave = (dia_anterior, p.rank)
            registros[chave]["numero_sucessores"] = len(filhos[p.rank])
            registros[chave]["ranks_sucessores"] = ";".join(
                map(str, filhos[p.rank])
            )
            registros[chave]["tipo_saida"] = (
                "sem_sucessor" if not filhos[p.rank] else
                "multiplos_sucessores" if len(filhos[p.rank]) > 1
                else "um_sucessor"
            )

        intersecoes_por_novo = defaultdict(float)
        for ra, rn, area in arestas:
            intersecoes_por_novo[rn] += area
        for p in nov:
            chave = (p.data, p.rank)
            pais_p = pais[p.rank]
            evento_id, tipo = mapa_eventos[p.rank]
            identidade = (
                linhagens[(dia_anterior, pais_p[0])]
                if tipo == "continuacao" else nova_linhagem(p.data)
            )
            linhagens[chave] = identidade
            registros[chave] = {
                "id_incendio": incendio, "data": p.data, "rank": p.rank,
                "id_patch_data": id_patch(p), "id_linhagem": identidade,
                "data_inicio_linhagem": inicio_linhagem[identidade],
                "tipo_entrada": tipo, "evento_entrada": evento_id,
                "numero_antecessores": len(pais_p),
                "ranks_antecessores": ";".join(map(str, pais_p)),
                "linhagens_antecessoras": ";".join(
                    linhagens[(dia_anterior, i)] for i in pais_p
                ), "area_laea_km2": p.area_m2 / 1e6,
                "area_herdada_anterior_pct": (
                    100 * intersecoes_por_novo[p.rank] / p.area_m2
                ), "numero_sucessores": None, "ranks_sucessores": "",
                "tipo_saida": None,
            }

        for ra, rn, area in arestas:
            evento_id, tipo = mapa_eventos[rn]
            vinculos.append({
                "id_incendio": incendio, "data_anterior": dia_anterior,
                "data_atual": dia_atual, "dias_intervalo": dias,
                "rank_anterior": ra, "rank_atual": rn,
                "id_patch_anterior": id_patch(por_rank_ant[ra]),
                "id_patch_atual": id_patch(por_rank_nov[rn]),
                "linhagem_anterior": linhagens[(dia_anterior, ra)],
                "linhagem_atual": linhagens[(dia_atual, rn)],
                "area_intersecao_km2": area / 1e6,
                "porcentagem_patch_anterior": (
                    100 * area / por_rank_ant[ra].area_m2
                ), "porcentagem_patch_atual": (
                    100 * area / por_rank_nov[rn].area_m2
                ), "id_evento": evento_id, "tipo_evento": tipo,
            })

        area_ant = sum(p.area_m2 for p in ant)
        area_nov = sum(p.area_m2 for p in nov)
        soma_intersecoes = sum(area for _, _, area in arestas)
        transicoes.append({
            "id_incendio": incendio, "data_anterior": dia_anterior,
            "data_atual": dia_atual, "dias_intervalo": dias,
            "patches_anteriores": len(ant), "patches_atuais": len(nov),
            "vinculos_por_area": len(arestas),
            **{f"eventos_{nome}": contagens[nome] for nome in (
                "continuacao", "convergencia", "divergencia", "reorganizacao",
                "surgimento_sem_sobreposicao", "sem_sucessor"
            )},
            "pares_contato_somente_pontual": contatos["pontual"],
            "pares_contato_somente_linear": contatos["linear"],
            "porcentagem_area_anterior_vinculada": (
                100 * soma_intersecoes / area_ant
            ), "porcentagem_area_atual_com_antecessor": (
                100 * soma_intersecoes / area_nov
            ), "area_acumulada_anterior_km2": area_ant / 1e6,
            "area_acumulada_atual_km2": area_nov / 1e6,
            "crescimento_liquido_km2": (area_nov - area_ant) / 1e6,
        })

    for p in por_data[datas[-1]]:
        registros[(p.data, p.rank)]["tipo_saida"] = "sem_observacao_posterior"

    linhas = [registros[(p.data, p.rank)] for dia in datas for p in por_data[dia]]
    totais = Counter(e["tipo_evento"] for e in eventos)
    resumo = {
        "id_incendio": incendio,
        "numero_registros_p1": len(patches),
        "numero_datas": len(datas),
        "numero_transicoes_observadas": len(transicoes),
        "data_inicial": datas[0], "data_final": datas[-1],
        "numero_linhagens_conservadoras": proximo_id,
        "numero_vinculos_area": len(vinculos),
        "numero_eventos_grafo": len(eventos),
        "eventos_por_tipo": dict(sorted(totais.items())),
        "limiar_area_intersecao_m2": area_minima_m2,
        "lacunas_temporais": [
            {"de": t["data_anterior"], "ate": t["data_atual"],
             "dias": t["dias_intervalo"]}
            for t in transicoes if t["dias_intervalo"] > 1
        ],
        "transicoes_com_convergencia": [
            {"de": t["data_anterior"], "ate": t["data_atual"],
             "eventos": t["eventos_convergencia"]}
            for t in transicoes if t["eventos_convergencia"] > 0
        ],
        "menor_retencao_area_anterior_pct": min(
            t["porcentagem_area_anterior_vinculada"] for t in transicoes
        ) if transicoes else None,
        "nota_interpretativa": (
            "Convergencia/divergencia classificam componentes do grafo de "
            "sobreposicao vetorial entre observacoes, nao fusoes ou novas "
            "ignicoes fisicas. Contatos sem area sao descartados como vinculo. "
            "Na primeira data, linhagens sao apenas linha de base; "
            "sem observacao posterior nao implica fim do incendio."
        ),
    }
    return linhas, vinculos, eventos, transicoes, resumo


def executar(caminho_p1: Path, pasta_saida: Path,
            area_minima_m2: float = 1.0) -> dict:
    patches = carregar_p1(caminho_p1)
    projecao, reparados = projetar_patches(patches)
    linhas, vinculos, eventos, transicoes, resumo = analisar_linhagens(
        patches, area_minima_m2
    )
    resumo.update({
        "projecao": projecao,
        "geometrias_reparadas_apos_projecao": reparados,
        "origem_p1": str(caminho_p1),
        "sha256_p1": sha256(caminho_p1.read_bytes()).hexdigest(),
    })
    pasta_saida.mkdir(parents=True, exist_ok=True)
    incendio = resumo["id_incendio"]
    for nome, campos, dados in (
        ("linhagens_patches", CAMPOS_LINHAGENS, linhas),
        ("vinculos_temporais", CAMPOS_VINCULOS, vinculos),
        ("eventos_topologicos", CAMPOS_EVENTOS, eventos),
        ("resumo_transicoes", CAMPOS_TRANSICOES, transicoes),
    ):
        salvar_csv(pasta_saida / f"{nome}_{incendio}.csv", campos, dados)

    # Camada de verificacao no QGIS: para cada evento N->1, exporta a
    # feicao do patch *atual* na geometria WGS84 ORIGINAL do P1.
    # Nenhum dissolve, alteracao topologica ou reinterpretacao raster.
    feicoes_origem = json.loads(caminho_p1.read_text(encoding="utf-8"))["features"]
    geometrias_origem = {
        (f["properties"]["data"], f["properties"]["rank"]): f["geometry"]
        for f in feicoes_origem
    }
    feicoes_convergencia = []
    for e in eventos:
        if e["tipo_evento"] != "convergencia":
            continue
        rank_atual = int(e["ranks_atuais"])
        feicoes_convergencia.append({
            "type": "Feature",
            "id": e["id_evento"],
            "geometry": geometrias_origem[(e["data_atual"], rank_atual)],
            "properties": {
                "id_incendio": incendio, "id_evento": e["id_evento"],
                "data_anterior": e["data_anterior"],
                "data_atual": e["data_atual"],
                "dias_intervalo": e["dias_intervalo"],
                "rank_atual": rank_atual,
                "numero_patches_anteriores": e["numero_patches_anteriores"],
                "ranks_anteriores": e["ranks_anteriores"],
                "area_anteriores_km2": e["area_anteriores_km2"],
                "area_atual_km2": e["area_atuais_km2"],
                "diferenca_areas_km2": e["diferenca_areas_km2"],
                "tipo_evento": e["tipo_evento"],
            },
        })
    (pasta_saida / f"convergencias_para_qgis_{incendio}.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feicoes_convergencia},
                   ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8"
    )
    resumo["numero_feicoes_geojson_convergencia"] = len(feicoes_convergencia)
    (pasta_saida / f"resumo_linhagens_{incendio}.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    return resumo


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("p1", type=Path, help="GeoJSON P1 validado")
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--area-minima-sobreposicao-m2", type=float, default=1.0,
                        help="limiar numerico de intersecao entre datas (default 1)")
    args = parser.parse_args()
    try:
        print(json.dumps(executar(
            args.p1, args.saida, args.area_minima_sobreposicao_m2
        ), ensure_ascii=False, indent=2))
    except (OSError, ValueError, json.JSONDecodeError, pyproj.ProjError) as exc:
        print(f"FALHA: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
