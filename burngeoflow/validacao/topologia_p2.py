"""Reconciliação topológica P2 versus P1 para análises TR/IGT.

As geometrias originais não são editadas. Um P2 inválido só é aceito após
`make_valid` se o polígono resultante concordar espacialmente com o P1
correspondente já projetado/validado, sob tolerância explícita de área simétrica.
As intervenções são registradas em cada resumo científico.
"""
from __future__ import annotations

import shapely
from shapely.validation import explain_validity


class ErroConciliacao(ValueError):
    """Incompatibilidade topológica entre P1 e P2."""


def _areal(geometria):
    """Extrai a parte areal de um retorno de make_valid sem inventar áreas."""
    if geometria.is_empty:
        return None
    if geometria.geom_type in ("Polygon", "MultiPolygon"):
        return geometria
    if geometria.geom_type == "GeometryCollection":
        poligonos = []
        for parte in geometria.geoms:
            resultado = _areal(parte)
            if resultado is not None:
                if resultado.geom_type == "Polygon":
                    poligonos.append(resultado)
                else:
                    poligonos.extend(resultado.geoms)
        return shapely.union_all(poligonos) if poligonos else None
    return None


def reconciliar_p2(geom_wgs84, patch_p1, transformador, *,
                   registro: int, data: str, rank: int) -> tuple[object, dict]:
    """Confere equivalência P2/P1 após a mesma projeção e reparo auditável.

    A saída geométrica é projetada e válida, mas não substitui os arquivos de
    entrada. Nos cálculos, o P1 projetado continua sendo a referência comum.
    """
    contexto = f"P2 registro {registro} ({data}, rank {rank})"
    esperado = patch_p1.geometria
    if esperado.is_empty or not esperado.is_valid or esperado.area <= 0:
        raise ErroConciliacao(f"{contexto}: P1 correspondente inválido")
    try:
        projetado = shapely.transform(
            geom_wgs84, transformador.transform, interleaved=False)
        valido_original = bool(projetado.is_valid)
        motivo = None if valido_original else explain_validity(projetado)
        comparador = projetado if valido_original else shapely.make_valid(projetado)
        comparador = _areal(comparador)
        if (comparador is None or comparador.is_empty
                or not comparador.is_valid or comparador.area <= 0):
            raise ErroConciliacao(
                f"{contexto}: reparo não produziu polígono válido; motivo={motivo}")
        divergencia = comparador.symmetric_difference(esperado).area
    except ErroConciliacao:
        raise
    except (shapely.GEOSException, ValueError) as exc:
        raise ErroConciliacao(
            f"{contexto}: falha na comparação topológica: {exc}") from exc
    limite = max(1.0, esperado.area * 1e-8)
    if divergencia > limite:
        raise ErroConciliacao(
            f"{contexto}: geometria P2 diverge do P1 mesmo após reparo; "
            f"diferenca_simetrica_m2={divergencia:.6f}, "
            f"tolerancia_m2={limite:.6f}, motivo_original={motivo}")
    return comparador, {
        "registro": registro, "data": data, "rank": rank,
        "reparo_p2_necessario": not valido_original,
        "motivo_original": motivo,
        "tipo_final": comparador.geom_type,
        "area_p1_projetada_m2": esperado.area,
        "area_p2_comparada_m2": comparador.area,
        "diferenca_simetrica_m2": divergencia,
        "tolerancia_m2": limite,
    }
