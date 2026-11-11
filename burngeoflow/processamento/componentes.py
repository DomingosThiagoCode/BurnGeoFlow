"""Organiza P1 por data e rank preservando os GeoJSONs originais."""
from __future__ import annotations
from collections import defaultdict
import json
from pathlib import Path

def agrupar_por_data(feature_collection: dict) -> dict[str, list[dict]]:
    if feature_collection.get("type") != "FeatureCollection":
        raise ValueError("Esperado GeoJSON FeatureCollection.")
    grupos: dict[str, list[dict]] = defaultdict(list)
    for i, feicao in enumerate(feature_collection.get("features", [])):
        propriedades = feicao.get("properties") or {}
        data, rank = propriedades.get("data"), propriedades.get("rank")
        if not isinstance(data, str) or rank is None:
            raise ValueError(f"Feição {i} sem data ou rank.")
        grupos[data].append(feicao)
    for patches in grupos.values():
        patches.sort(key=lambda f: int(f["properties"]["rank"]))
    return dict(sorted(grupos.items()))

def carregar_p1(arquivo: Path) -> dict[str, list[dict]]:
    with Path(arquivo).open(encoding="utf-8") as f:
        dados = json.load(f)
    return agrupar_por_data(dados)
