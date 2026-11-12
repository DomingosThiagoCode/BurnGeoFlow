"""Leitura rápida, somente leitura, dos resultados espaciais do BurnGeoFlow.

Nenhuma função aciona Earth Engine, executa o pipeline ou escreve nos
GeoJSONs originais. Os dados são publicados para uma interface local.
"""
from __future__ import annotations

import csv
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


class ErroVisualizador(ValueError):
    """Insumos ausentes, misturados ou inconsistentes para a visualização."""


def caminhos(base: Path, incendio: int) -> dict[str, Path]:
    if not isinstance(incendio, int) or incendio <= 0:
        raise ErroVisualizador("ID do incêndio deve ser inteiro positivo")
    raiz = base / str(incendio)
    originais = raiz / "dados" / f"estudo_caso_{incendio}"
    e5 = raiz / "resultados" / "etapa5"
    e6 = raiz / "resultados" / "etapa6"
    return {
        "raiz": raiz,
        "p1": originais / f"P1_componentes_{incendio}.geojson",
        "p2": originais / f"P2_regiao_movel_{incendio}.geojson",
        "serie": e5 / f"serie_diaria_integrada_{incendio}.csv",
        "transicoes": e5 / f"transicoes_integradas_{incendio}.csv",
        "resumo5": e5 / f"resumo_etapa5_{incendio}.json",
        "resumo6": e6 / f"resumo_validacao_{incendio}.json",
    }


def descobrir_eventos(base: Path) -> list[int]:
    """Descobre IDs com pelo menos o par de GeoJSONs locais."""
    if not base.is_dir():
        return []
    eventos = []
    for pasta in base.iterdir():
        if not pasta.is_dir() or not pasta.name.isdecimal():
            continue
        incendio = int(pasta.name)
        paths = caminhos(base, incendio)
        if paths["p1"].is_file() and paths["p2"].is_file():
            eventos.append(incendio)
    return sorted(eventos)


def assinatura_arquivos(paths: dict[str, Path]) -> tuple:
    """Chave de cache por tamanho/data de modificação, sem conteúdo pesado."""
    return tuple(
        (nome, str(caminho), caminho.stat().st_size,
         caminho.stat().st_mtime_ns)
        if caminho.is_file() else (nome, str(caminho), None, None)
        for nome, caminho in paths.items() if nome != "raiz"
    )


def _json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, UnicodeError, OSError) as exc:
        raise ErroVisualizador(f"JSON inválido: {path}: {exc}") from exc


def _csv(path: Path) -> list[dict]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except (ValueError, UnicodeError, OSError) as exc:
        raise ErroVisualizador(f"CSV inválido: {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def _indexar_geojson(path: Path, incendio: int, *, unico: bool):
    origem = _json(path)
    if origem.get("type") != "FeatureCollection":
        raise ErroVisualizador(f"Não é FeatureCollection: {path}")
    features = origem.get("features")
    if not isinstance(features, list) or not features:
        raise ErroVisualizador(f"GeoJSON sem feições: {path}")
    indice = {}
    for i, feat in enumerate(features):
        prop = feat.get("properties") or {}
        dia = prop.get("data")
        geom = feat.get("geometry") or {}
        try:
            id_lido = int(prop.get("id_incendio"))
        except (TypeError, ValueError) as exc:
            raise ErroVisualizador(
                f"{path.name}, feição {i}: ID inválido"
            ) from exc
        if id_lido != incendio or not isinstance(dia, str) or not dia:
            raise ErroVisualizador(
                f"{path.name}, feição {i}: ID/data incompatível"
            )
        if geom.get("type") not in ("Polygon", "MultiPolygon"):
            raise ErroVisualizador(
                f"{path.name}, feição {i}: esperava geometria poligonal"
            )
        indice.setdefault(dia, []).append(feat)
        if unico and len(indice[dia]) != 1:
            raise ErroVisualizador(
                f"{path.name}: P2 possui mais de uma feição em {dia}"
            )
    return indice


def carregar_evento(base: Path, incendio: int) -> dict:
    """Abre P1/P2 e, quando disponíveis, resultados integrados e auditoria."""
    paths = caminhos(base, incendio)
    if not paths["p1"].is_file() or not paths["p2"].is_file():
        raise ErroVisualizador(
            f"ID {incendio} não possui P1/P2 locais. "
            "Execute primeiro python executar_pipeline.py --id "
            f"{incendio} --origem gee [--ano ANO]."
        )
    p1 = _indexar_geojson(paths["p1"], incendio, unico=False)
    p2_agrupado = _indexar_geojson(paths["p2"], incendio, unico=True)
    datas = sorted(p1)
    if set(datas) != set(p2_agrupado):
        raise ErroVisualizador(
            "P1/P2 possuem conjuntos de datas diferentes"
        )
    p2 = {dia: p2_agrupado[dia][0] for dia in datas}
    serie = _csv(paths["serie"]) if paths["serie"].is_file() else []
    trans = _csv(paths["transicoes"]) if paths["transicoes"].is_file() else []
    resumo5 = _json(paths["resumo5"]) if paths["resumo5"].is_file() else {}
    resumo6 = _json(paths["resumo6"]) if paths["resumo6"].is_file() else {}
    if serie:
        datas_csv = [r.get("data") for r in serie]
        if len(set(datas_csv)) != len(datas_csv) or set(datas_csv) != set(datas):
            raise ErroVisualizador(
                "A série temporal da Etapa 5 não corresponde às datas P1/P2"
            )
        if any(int(r["id_incendio"]) != incendio for r in serie):
            raise ErroVisualizador("Série temporal pertence a outro incêndio")
        serie.sort(key=lambda r: r["data"])
    if trans:
        if len(trans) != len(datas)-1:
            raise ErroVisualizador("Transições da Etapa 5 incompletas")
        pares_esperados = list(zip(datas, datas[1:]))
        trans.sort(key=lambda r: (r["data_anterior"], r["data_atual"]))
        pares_reais = [(r["data_anterior"], r["data_atual"]) for r in trans]
        if pares_esperados != pares_reais:
            raise ErroVisualizador("Transições não correspondem às datas")
    for nome, dados in (("resumo5", resumo5), ("resumo6", resumo6)):
        if dados and int(dados["id_incendio"]) != incendio:
            raise ErroVisualizador(f"{nome} pertence a outro incêndio")
    # Impede visualização de resultados científicos misturados com outros
    # P1/P2. O mapa permanece disponível quando a Etapa 5 ainda não existe.
    if resumo5:
        for nome in ("p1", "p2"):
            esperado = resumo5.get(f"sha256_{nome}")
            if esperado and esperado != _sha256(paths[nome]):
                raise ErroVisualizador(
                    f"Entrada {nome.upper()} alterada após a Etapa 5. "
                    "Não exibir métricas possivelmente desatualizadas."
                )
    return {
        "id_incendio": incendio,
        "datas": datas,
        "p1_por_data": p1,
        "p2_por_data": p2,
        "serie": serie,
        "transicoes": trans,
        "resumo5": resumo5,
        "resumo6": resumo6,
        "completo": bool(serie and trans and resumo5 and resumo6),
    }


def _pontos(coordenadas):
    if (
        isinstance(coordenadas, (list, tuple))
        and len(coordenadas) >= 2
        and isinstance(coordenadas[0], (int, float))
        and isinstance(coordenadas[1], (int, float))
    ):
        yield float(coordenadas[0]), float(coordenadas[1])
    elif isinstance(coordenadas, (list, tuple)):
        for parte in coordenadas:
            yield from _pontos(parte)


def limites_dia(features: list[dict]) -> tuple[float, float, float, float]:
    pontos = (
        ponto for feature in features
        for ponto in _pontos(feature["geometry"]["coordinates"])
    )
    minx = miny = float("inf")
    maxx = maxy = float("-inf")
    for lon, lat in pontos:
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ErroVisualizador("Coordenada fora de EPSG:4326")
        minx, miny = min(minx, lon), min(miny, lat)
        maxx, maxy = max(maxx, lon), max(maxy, lat)
    if minx == float("inf"):
        raise ErroVisualizador("Geometria sem coordenadas")
    return minx, miny, maxx, maxy


def camada_dia(evento: dict, dia: str, *, incluir_p1=True,
                incluir_p2=True) -> dict:
    if dia not in evento["p1_por_data"]:
        raise ErroVisualizador(f"Data ausente: {dia}")
    features = []
    if incluir_p1:
        features.extend(evento["p1_por_data"][dia])
    if incluir_p2:
        features.append(evento["p2_por_data"][dia])
    return {"type": "FeatureCollection", "features": features}


def linha_dia(evento: dict, dia: str) -> dict | None:
    return next((r for r in evento["serie"] if r["data"] == dia), None)


def transicao_para(evento: dict, dia: str) -> dict | None:
    return next((
        r for r in evento["transicoes"] if r["data_atual"] == dia
    ), None)
