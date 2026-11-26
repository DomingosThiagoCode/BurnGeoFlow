"""Conectividade geométrica, incluindo contato somente por vértice.

A saída são grupos derivados, sem alteração do P1 original.
Não representa necessariamente passagem física do fogo.
"""
from __future__ import annotations
from collections.abc import Sequence
from typing import Any
from shapely import STRtree

def grupos_conectados(geometrias: Sequence[Any]) -> list[list[int]]:
    """Lista índices de feições conectadas por interseção geométrica.

    intersects() inclui contatos por vértice e borda.
    Índice espacial para reduzir comparações de pares disjuntos.
    """
    n = len(geometrias)
    pais = list(range(n))
    def raiz(i: int) -> int:
        while pais[i] != i:
            pais[i] = pais[pais[i]]
            i = pais[i]
        return i
    def unir(i: int, j: int) -> None:
        a, b = raiz(i), raiz(j)
        if a != b:
            pais[max(a, b)] = min(a, b)
    for i, geom in enumerate(geometrias):
        if geom is None or geom.is_empty:
            raise ValueError(f"Geometria vazia ou ausente no índice {i}.")
    arvore = STRtree(geometrias)
    for i, geom in enumerate(geometrias):
        for j in arvore.query(geom, predicate="intersects"):
            if int(j) < i:
                unir(i, int(j))
    grupos: dict[int, list[int]] = {}
    for i in range(n):
        grupos.setdefault(raiz(i), []).append(i)
    return sorted(grupos.values(), key=lambda indices: indices[0])
