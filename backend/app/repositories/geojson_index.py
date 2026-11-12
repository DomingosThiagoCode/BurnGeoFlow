"""Índice espacial derivado e reconstruível, organizado por data e camada.

A primeira indexação percorre o GeoJSON em streaming com ijson, com memória
limitada ao tamanho de uma feição. A consulta lê somente a data selecionada.
P1/P2 originais nunca são alterados; os índices são exclusivamente cache.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from threading import Lock
from typing import Iterator

import ijson

from backend.app.core.errors import DadosInconsistentes, EntradaInvalida

_LOCK = Lock()
DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VERSAO = 1


def validar_data(texto: str) -> str:
    if not DATA.fullmatch(texto):
        raise EntradaInvalida("Data deve seguir YYYY-MM-DD")
    try:
        if date.fromisoformat(texto).isoformat() != texto:
            raise ValueError("Data não canônica")
    except ValueError as exc:
        raise EntradaInvalida("Data inexistente ou inválida") from exc
    return texto


def calcular_hash(caminho: Path) -> str:
    h = sha256()
    with caminho.open("rb") as arq:
        for bloco in iter(lambda: arq.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


class IndiceGeoJSON:
    """Índice materializado com invalidação por assinatura de arquivo.

    Assume o processo API local com um worker (índice com lock por processo).
    Não usar vários processos de indexação concorrentes nesta versão.
    """

    def __init__(self, raiz_execucao: Path):
        self.raiz = raiz_execucao

    def _destino(self, layer: str, caminho: Path) -> tuple[Path, dict]:
        if layer not in ("p1", "p2"):
            raise EntradaInvalida("Camada deve ser p1 ou p2")
        stat = caminho.stat()
        identidade = {
            "versao": VERSAO,
            "tamanho": stat.st_size,
            "modificado_ns": stat.st_mtime_ns,
        }
        nome = f"{layer}-{stat.st_size:x}-{stat.st_mtime_ns:x}"
        return self.raiz / ".visualizador_index" / nome, identidade

    def _manifesto(self, destino: Path, assinatura: dict,
                   esperado_sha: str | None) -> dict | None:
        manifest = destino / "manifest.json"
        if not manifest.is_file():
            return None
        try:
            doc = json.loads(manifest.read_text(encoding="utf-8"))
            if doc.get("fonte") != assinatura:
                return None
            if esperado_sha and doc.get("sha256") != esperado_sha:
                raise DadosInconsistentes(
                    "GeoJSON mudou em relação ao SHA-256 da Etapa 5"
                )
            for data_str in doc.get("datas", {}):
                validar_data(data_str)
                if not (destino / (data_str + ".jsonl")).is_file():
                    return None
            return doc
        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            return None

    def obter(self, layer: str, caminho: Path, id_incendio: int,
              esperado_sha: str | None = None) -> tuple[Path, dict]:
        if not caminho.is_file():
            raise DadosInconsistentes(
                f"GeoJSON obrigatório ausente: {caminho.name}"
            )
        with _LOCK:
            destino, identidade = self._destino(layer, caminho)
            pronto = self._manifesto(destino, identidade, esperado_sha)
            if pronto is not None:
                return destino, pronto
            pasta_cache = destino.parent
            pasta_cache.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(
                prefix=".indexando-", dir=pasta_cache,
            ))
            try:
                contagens = {}
                try:
                    with caminho.open("rb") as arq:
                        for i, feat in enumerate(
                            ijson.items(arq, "features.item", use_float=True)
                        ):
                            if not isinstance(feat, dict):
                                raise DadosInconsistentes(
                                    f"GeoJSON {layer} tem feição inválida {i}"
                                )
                            props = feat.get("properties")
                            geom = feat.get("geometry")
                            if not isinstance(props, dict) or not isinstance(geom, dict):
                                raise DadosInconsistentes(
                                    f"{layer}: feição {i} sem geometria/propriedades"
                                )
                            dia = validar_data(str(props.get("data", "")))
                            try:
                                id_feicao = int(props.get("id_incendio", -1))
                            except (ValueError, TypeError) as exc:
                                raise DadosInconsistentes(
                                    f"{layer}: ID inválido na feição {i}"
                                ) from exc
                            if (
                                id_feicao != id_incendio
                                or geom.get("type") not in ("Polygon", "MultiPolygon")
                            ):
                                raise DadosInconsistentes(
                                    f"{layer}: feição {i}, ID ou geometria incompatível"
                                )
                            contagens[dia] = contagens.get(dia, 0) + 1
                            if layer == "p2" and contagens[dia] != 1:
                                raise DadosInconsistentes(
                                    f"P2 tem mais de uma feição em {dia}"
                                )
                            with (stage / f"{dia}.jsonl").open(
                                "a", encoding="utf-8",
                            ) as out:
                                out.write(
                                    json.dumps(feat, ensure_ascii=False,
                                               separators=(",", ":"), allow_nan=False)
                                    + "\n"
                                )
                except (ijson.JSONError, UnicodeError, OverflowError) as exc:
                    raise DadosInconsistentes(
                        f"GeoJSON {layer} ilegível: {type(exc).__name__}: {exc}"
                    ) from exc
                if not contagens:
                    raise DadosInconsistentes(f"GeoJSON {layer} sem feições")
                # Conferência posterior à leitura: recusa indexar arquivo
                # alterado durante o processamento.
                _, depois = self._destino(layer, caminho)
                if depois != identidade:
                    raise DadosInconsistentes(
                        f"Arquivo {layer.upper()} mudou durante a indexação"
                    )
                digest = calcular_hash(caminho)
                if esperado_sha and digest != esperado_sha:
                    raise DadosInconsistentes(
                        f"SHA-256 de {layer.upper()} difere da Etapa 5"
                    )
                manifesto = {
                    "fonte": identidade, "sha256": digest,
                    "id_incendio": id_incendio,
                    "camada": layer, "datas": dict(sorted(contagens.items())),
                }
                (stage / "manifest.json").write_text(
                    json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                if destino.exists():
                    # É um cache derivado da API, nunca a pasta de origem.
                    if destino.parent != pasta_cache:
                        raise DadosInconsistentes("Destino de índice inválido")
                    shutil.rmtree(destino)
                os.replace(stage, destino)
                return destino, manifesto
            finally:
                if stage.exists():
                    shutil.rmtree(stage, ignore_errors=True)

    @staticmethod
    def iterar_geojson(pasta: Path, dia: str) -> Iterator[bytes]:
        """Produz um FeatureCollection sem materializar a data em RAM."""
        validar_data(dia)
        arquivo = pasta / f"{dia}.jsonl"
        yield b'{"type":"FeatureCollection","features":['
        with arquivo.open("rb") as arq:
            for i, linha in enumerate(arq):
                if i:
                    yield b","
                yield linha.rstrip(b"\n")
        yield b"]}"
