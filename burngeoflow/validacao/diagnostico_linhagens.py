"""Diagnóstico não destrutivo para excesso de interseções nas linhagens do P1.

Utilizado SOMENTE quando uma invariante já existente falha. Não muda limiares,
geometrias, rank, vínculos ou o resultado do processamento científico.
"""
from __future__ import annotations

import shapely

from burngeoflow.analises.paisagem import Patch


class ExcessoIntersecoes(ValueError):
    """Falha científica com evidência geométrica serializável em JSON."""

    def __init__(self, mensagem: str, diagnostico: dict):
        super().__init__(mensagem)
        self.diagnostico = diagnostico


def diagnosticar_intersecoes(
    patch: Patch,
    opostos: list[Patch],
    arestas: list[tuple[int, int, float]],
    lado: str,
    limiar_m2: float,
) -> dict:
    """Recalcula só as interseções do patch suspeito, na LAEA já existente.

    A soma pode exceder a área do patch se patches *do outro dia* se
    sobrepuserem dentro dele; a união mede a área sem contagem duplicada.
    O diagnóstico não decide a causa nem modifica qualquer geometria.
    """
    if lado not in ("anterior", "atual"):
        raise ValueError("Lado da transição inválido.")
    pares = [
        (b if lado == "anterior" else a, float(area))
        for a, b, area in arestas
        if (a if lado == "anterior" else b) == patch.rank
    ]
    por_rank = {p.rank: p for p in opostos}
    intersecoes = []
    contribuicoes = []
    for rank, area_registrada in pares:
        outro = por_rank[rank]
        geom = patch.geometria.intersection(outro.geometria)
        intersecoes.append(geom)
        contribuicoes.append({
            "rank_oposto": rank,
            "data_oposta": outro.data,
            "area_intersecao_m2": geom.area,
            "area_intersecao_registrada_m2": area_registrada,
            "area_patch_oposto_m2": outro.area_m2,
            "patch_oposto_reparado_apos_projecao": bool(
                outro.reparado_apos_projecao
            ),
        })
    soma = sum(x["area_intersecao_m2"] for x in contribuicoes)
    uniao = shapely.union_all(intersecoes).area if intersecoes else 0.0
    area = patch.area_m2
    tolerancia = max(1.0, area * 1e-8)

    # Investiga somente as interseções do patch suspeito, e apenas na falha.
    # O STRtree limita a busca em casos de muitos sucessores/antecessores.
    pares_sobrepostos = []
    n_pares_sobrepostos = 0
    if len(intersecoes) > 1:
        arvore = shapely.STRtree(intersecoes)
        for i, geom in enumerate(intersecoes):
            for j in arvore.query(geom, predicate="intersects"):
                j = int(j)
                if j <= i:
                    continue
                area_dupla = geom.intersection(intersecoes[j]).area
                if area_dupla > 0:
                    n_pares_sobrepostos += 1
                    if len(pares_sobrepostos) < 30:
                        pares_sobrepostos.append({
                            "ranks_opostos": [
                                contribuicoes[i]["rank_oposto"],
                                contribuicoes[j]["rank_oposto"],
                            ],
                            "area_comum_m2": area_dupla,
                        })

    contribuicoes.sort(
        key=lambda x: (-x["area_intersecao_m2"], x["rank_oposto"])
    )
    duplicada = max(0.0, soma - uniao)
    excesso = max(0.0, soma - area)
    return {
        "tipo": "excesso_soma_intersecoes_p1",
        "id_incendio": patch.incendio,
        "lado_patch": lado,
        "data_patch": patch.data,
        "rank_patch": patch.rank,
        "data_oposta": opostos[0].data if opostos else None,
        "area_patch_laea_m2": area,
        "area_patch_atributo_gee_km2": patch.area_gee_km2,
        "patch_reparado_apos_projecao": bool(patch.reparado_apos_projecao),
        "bounds_patch_laea_m": list(patch.geometria.bounds),
        "area_minima_vinculo_m2": limiar_m2,
        "limiar_erro_existente_m2": tolerancia,
        "numero_intersecoes": len(contribuicoes),
        "soma_intersecoes_m2": soma,
        "uniao_intersecoes_m2": uniao,
        "area_contada_repetidamente_m2": duplicada,
        "excesso_soma_sobre_patch_m2": excesso,
        "excesso_relativo_patch_pct": 100 * excesso / area if area else None,
        "area_patch_nao_coberta_pela_uniao_m2": max(0.0, area - uniao),
        "uniao_maior_que_patch_apos_projecao": uniao > area + tolerancia,
        "numero_pares_sobrepostos": n_pares_sobrepostos,
        "amostra_pares_sobrepostos": pares_sobrepostos,
        "intersecoes_por_rank_oposto": contribuicoes,
        "evidencia_sobreposicao_entre_opostos": duplicada > tolerancia,
        "observacao": (
            "Evidência numérica em LAEA, não diagnóstico causal. "
            "Comparar com o P1 bruto, auditoria espacial e reparos da projeção. "
            "Não recalcular vínculos usando união nem suprimir a falha."
        ),
    }
