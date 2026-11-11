"""Conectividade geométrica, incluindo contato somente por vértice.

A saída são grupos derivados, sem alteração do P1 original.
Não representa necessariamente passagem física do fogo.
"""
from __future__ import annotations
from collections.abc import Sequence
from typing import Any

def grupos_conectados(geometrias: Sequence[Any]) -> list[list[int]]:
    """Lista índices de feições conectadas por interseção geométrica.

    intersects() inclui contatos por vértice e borda.
    Referência O(n²); otimização espacial pertence à etapa 7.3.
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
        for j in range(i):
            if geom.intersects(geometrias[j]):
                unir(i, j)
    grupos: dict[int, list[int]] = {}
    for i in range(n):
        grupos.setdefault(raiz(i), []).append(i)
    return sorted(grupos.values(), key=lambda indices: indices[0])
