"""Partição topológica EXPERIMENTAL de componentes P1 sobrepostos.

D-002, D-013, D-014. Ferramenta de diagnóstico sem política de reparação:
não faz snap, buffer, simplificação, arbitragem de faces nem alteração dos
dados científicos. Recebe geometrias poligonais JÁ VÁLIDAS em CRS métrico,
preferencialmente LAEA. Não reprojeta e não corrige a validade dos insumos.

A área de uma face coberta por N componentes é contada uma vez para
cobertura da união, mas N vezes na soma dos componentes originais.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from math import isfinite

import shapely
from shapely.geometry import MultiPolygon, Polygon, mapping
from shapely.ops import polygonize


def auditar_faces(
    componentes: Sequence[tuple[int, Polygon | MultiPolygon]],
    *,
    com_geometrias: bool = False,
) -> dict:
    """Particiona as bordas do conjunto e audita multiplicidade de cobertura.

    `ranks_cobertura` indica cobertura espacial, NÃO atribuição de uma face
    a um único componente. O fechamento é reportado numericamente, sem
    inventar uma tolerância de aceitação.

    Custo: a construção das faces e overlays pode ser intensiva; aplicar
    inicialmente apenas ao recorte focal de #44, não às 30.795 feições.
    """
    partes = list(componentes)
    if not partes:
        raise ValueError("A auditoria exige ao menos um componente")
    ranks = [rank for rank, _ in partes]
    if (
        len(ranks) != len(set(ranks))
        or any(type(rank) is not int or rank <= 0 for rank in ranks)
    ):
        raise ValueError("Ranks devem ser inteiros positivos e únicos")
    for rank, geom in partes:
        if (
            not isinstance(geom, (Polygon, MultiPolygon))
            or geom.is_empty
            or not geom.is_valid
            or not isfinite(geom.area)
            or geom.area <= 0
        ):
            raise ValueError(
                f"Rank {rank}: geometria poligonal válida de área positiva é obrigatória"
            )

    geometrias = [g for _, g in partes]
    # union_all sobre CONTORNOS para criar todos os nós de cruzamento.
    # Não é uma união dos polígonos nem uma partição atributiva aprovada.
    linhas_nodadas = shapely.union_all([g.boundary for g in geometrias])
    faces = polygonize(linhas_nodadas)
    indice = shapely.STRtree(geometrias)

    detalhes = []
    por_cobertura = defaultdict(float)
    area_faces = 0.0
    area_compartilhada = 0.0
    area_repetida = 0.0
    for face in faces:
        ponto = face.representative_point()
        # O ponto é interior; evita classificar por contato com bordas.
        cobertura = sorted(
            ranks[int(i)] for i in indice.query(ponto, predicate="within")
        )
        if not cobertura:
            # Face de buraco interior: fora da cobertura original.
            continue
        area = face.area
        area_faces += area
        por_cobertura[tuple(cobertura)] += area
        if len(cobertura) > 1:
            area_compartilhada += area
            area_repetida += (len(cobertura) - 1) * area

        item = {"ranks_cobertura": cobertura, "area_m2": area}
        if com_geometrias:
            item["geometria"] = mapping(face)
        detalhes.append(item)

    area_uniao = shapely.union_all(geometrias).area
    soma_areas = sum(g.area for g in geometrias)
    return {
        "quantidade_componentes": len(partes),
        "quantidade_faces": len(detalhes),
        "area_soma_componentes_m2": soma_areas,
        "area_uniao_m2": area_uniao,
        "area_faces_sem_dupla_contagem_m2": area_faces,
        "area_faces_compartilhadas_m2": area_compartilhada,
        "area_contada_repetidamente_m2": area_repetida,
        "residuo_particao_m2": area_faces - area_uniao,
        "residuo_multiplicidade_m2": area_faces + area_repetida - soma_areas,
        "faces_por_conjunto_de_ranks": [
            {"ranks_cobertura": list(rs), "area_m2": area}
            for rs, area in sorted(por_cobertura.items())
        ],
        "faces": detalhes,
        "politica_atribuicao": (
            "INDEFINIDA: nenhuma face compartilhada foi atribuída, "
            "removida ou corrigida"
        ),
    }
