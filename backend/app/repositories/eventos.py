"""Repositório de leitura de execuções locais; nenhuma alteração no pipeline."""
from __future__ import annotations

import csv
from datetime import date
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from backend.app.core.errors import DadosInconsistentes, EventoNaoEncontrado
from backend.app.repositories.geojson_index import IndiceGeoJSON, validar_data


@lru_cache(maxsize=128)
def _ler_tabela_cache(caminho: str, tamanho: int, modificado_ns: int) -> tuple:
    with Path(caminho).open(encoding="utf-8-sig", newline="") as arq:
        rows = list(csv.DictReader(arq))
    return tuple(tuple(row.items()) for row in rows)


@lru_cache(maxsize=128)
def _ler_json_cache(caminho: str, tamanho: int, modificado_ns: int) -> dict:
    with Path(caminho).open(encoding="utf-8") as arq:
        obj = json.load(arq)
    if not isinstance(obj, dict):
        raise DadosInconsistentes(f"JSON não é objeto: {caminho}")
    return obj


@lru_cache(maxsize=128)
def _sha_cache(caminho: str, tamanho: int, modificado_ns: int) -> str:
    h = sha256()
    with Path(caminho).open("rb") as arq:
        for bloco in iter(lambda: arq.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def _hash_arquivo(caminho: Path) -> str:
    s = caminho.stat()
    return _sha_cache(str(caminho), s.st_size, s.st_mtime_ns)


def _csv_rows(caminho: Path) -> list[dict]:
    if not caminho.is_file():
        return []
    s = caminho.stat()
    return [dict(t) for t in _ler_tabela_cache(
        str(caminho), s.st_size, s.st_mtime_ns,
    )]


def _json_obj(caminho: Path) -> dict:
    if not caminho.is_file():
        return {}
    s = caminho.stat()
    return dict(_ler_json_cache(
        str(caminho), s.st_size, s.st_mtime_ns,
    ))


class RepositorioEventos:
    """Filesystem é a fonte da verdade. SQLite só fará sentido para jobs."""

    def __init__(self, execucoes: Path):
        self.base = Path(execucoes).expanduser().resolve()

    def arquivos(self, incendio: int) -> dict[str, Path]:
        if not isinstance(incendio, int) or incendio <= 0:
            raise EventoNaoEncontrado("ID de evento inválido")
        raiz = self.base / str(incendio)
        dados = raiz / "dados" / f"estudo_caso_{incendio}"
        resultados = raiz / "resultados"
        return {
            "raiz": raiz,
            "p1": dados / f"P1_componentes_{incendio}.geojson",
            "p2": dados / f"P2_regiao_movel_{incendio}.geojson",
            "serie": resultados / "etapa5" / f"serie_diaria_integrada_{incendio}.csv",
            "transicoes": resultados / "etapa5" / f"transicoes_integradas_{incendio}.csv",
            "resumo5": resultados / "etapa5" / f"resumo_etapa5_{incendio}.json",
            "resumo6": resultados / "etapa6" / f"resumo_validacao_{incendio}.json",
            "resumo4": resultados / "etapa4" / f"resumo_regiao_movel_{incendio}.json",
            "pontos_tr": resultados / "etapa4" / f"pontos_representativos_{incendio}.csv",
            "segmentos_tr": resultados / "etapa4" / f"segmentos_trajetorias_{incendio}.csv",
            "indicadores_tr": resultados / "etapa4" / f"indicadores_regiao_{incendio}.csv",
        }

    def _obrigatorios(self, incendio: int) -> dict[str, Path]:
        arquivos = self.arquivos(incendio)
        if not arquivos["p1"].is_file() or not arquivos["p2"].is_file():
            raise EventoNaoEncontrado(
                f"ID {incendio}: P1/P2 não encontrados. "
                "Execute primeiro o pipeline."
            )
        return arquivos

    def listar(self) -> list[int]:
        if not self.base.is_dir():
            return []
        ids = []
        for pasta in self.base.iterdir():
            if not pasta.is_dir() or not pasta.name.isdecimal():
                continue
            numero = int(pasta.name)
            try:
                self._obrigatorios(numero)
            except EventoNaoEncontrado:
                continue
            ids.append(numero)
        return sorted(set(ids))

    def _resumos(self, arquivos: dict[str, Path], incendio: int):
        r5 = _json_obj(arquivos["resumo5"])
        r6 = _json_obj(arquivos["resumo6"])
        for doc in (r5, r6):
            if doc and doc.get("id_incendio") != incendio:
                raise DadosInconsistentes("Resumo de outro ID no diretório")
        return r5, r6

    def _proveniencia(self, arquivos: dict[str, Path], resumo5: dict):
        for nome in ("p1", "p2"):
            esperado = resumo5.get(f"sha256_{nome}")
            if esperado and _hash_arquivo(arquivos[nome]) != esperado:
                raise DadosInconsistentes(
                    f"{nome.upper()} não corresponde ao SHA-256 da Etapa 5"
                )

    def series(self, incendio: int) -> list[dict]:
        arquivos = self._obrigatorios(incendio)
        r5, _ = self._resumos(arquivos, incendio)
        if r5:
            self._proveniencia(arquivos, r5)
        linhas = _csv_rows(arquivos["serie"])
        if linhas:
            datas = [row.get("data") for row in linhas]
            if len(set(datas)) != len(datas):
                raise DadosInconsistentes("Datas duplicadas na série")
            if any(int(row["id_incendio"]) != incendio for row in linhas):
                raise DadosInconsistentes("Série de outro incêndio")
            linhas.sort(key=lambda x: x["data"])
        return linhas

    def transicoes(self, incendio: int) -> list[dict]:
        arquivos = self._obrigatorios(incendio)
        r5, _ = self._resumos(arquivos, incendio)
        if r5:
            self._proveniencia(arquivos, r5)
        trans = _csv_rows(arquivos["transicoes"])
        if trans:
            if any(int(row["id_incendio"]) != incendio for row in trans):
                raise DadosInconsistentes("Transições de outro incêndio")
            trans.sort(key=lambda x: (x["data_anterior"], x["data_atual"]))
            datas = [row["data"] for row in self.series(incendio)]
            if datas and list(zip(datas, datas[1:])) != [
                (r["data_anterior"], r["data_atual"]) for r in trans
            ]:
                raise DadosInconsistentes("Transições e série têm datas diferentes")
        return trans

    def resumo(self, incendio: int) -> dict:
        arquivos = self._obrigatorios(incendio)
        r5, r6 = self._resumos(arquivos, incendio)
        if r5:
            self._proveniencia(arquivos, r5)
        serie = _csv_rows(arquivos["serie"])
        if serie:
            datas = sorted(row["data"] for row in serie)
        else:
            indice, manifest = IndiceGeoJSON(
                arquivos["raiz"]
            ).obter("p1", arquivos["p1"], incendio)
            datas = sorted(manifest["datas"])
        if len(set(datas)) != len(datas):
            raise DadosInconsistentes("Datas duplicadas")
        return {
            "id_incendio": incendio,
            "datas": datas,
            "periodo_inicio": datas[0] if datas else None,
            "periodo_fim": datas[-1] if datas else None,
            "total_datas": len(datas),
            "tem_series": bool(serie),
            "tem_transicoes": arquivos["transicoes"].is_file(),
            "status_cientifico": r6.get("status_cientifico", "sem_analise"),
            "validacao_externa_concluida": bool(
                r6.get("validacao_externa_concluida", False)
            ),
            "dias_sobreposicao_p1_pendentes": r6.get(
                "dias_sobreposicao_p1_acima_1m2", []
            ),
            "observacao": (
                "Análise espacial descritiva. A existência de métricas "
                "não comprova validação científica externa."
            ),
        }


    def analise_regiao(self, incendio: int) -> dict:
        """Expõe saídas originais da Etapa 4 somente com proveniência consistente.

        Nunca recalcula indicadores e não combina arquivos históricos com
        geometrias P1/P2 de outra execução.
        """
        arqs = self._obrigatorios(incendio)
        chaves = ("resumo4", "pontos_tr", "segmentos_tr", "indicadores_tr")
        if not all(arqs[k].is_file() for k in chaves):
            return {"disponivel": False, "pontos": [],
                    "segmentos": [], "indicadores": []}
        meta = _json_obj(arqs["resumo4"])
        if int(meta.get("id_incendio", -1)) != incendio:
            raise DadosInconsistentes("Resumo da Etapa 4 pertence a outro evento")
        if not meta.get("sha256_p1") or not meta.get("sha256_p2"):
            raise DadosInconsistentes("Etapa 4 sem hashes de P1/P2")
        self._proveniencia(arqs, meta)

        pontos = _csv_rows(arqs["pontos_tr"])
        segmentos = _csv_rows(arqs["segmentos_tr"])
        indicadores = _csv_rows(arqs["indicadores_tr"])
        datas = self.resumo(incendio)["datas"]
        pares = list(zip(datas, datas[1:]))
        tipos = {"centroide", "norte", "sul", "leste", "oeste"}

        if not datas or len(pontos) != len(datas)*5 or len(segmentos) != len(pares)*5 or len(indicadores) != len(pares):
            raise DadosInconsistentes("Contagens da Etapa 4 incompatíveis com P1/P2")
        for grupo in (pontos, segmentos, indicadores):
            if any(int(r.get("id_incendio", -1)) != incendio for r in grupo):
                raise DadosInconsistentes("Etapa 4 contém registros de outro evento")
        if set((r.get("data"), r.get("ponto")) for r in pontos) != {
            (d, tipo) for d in datas for tipo in tipos
        }:
            raise DadosInconsistentes("Pontos da Etapa 4 não correspondem às datas do evento")
        if set((r.get("data_anterior"), r.get("data_atual"), r.get("ponto")) for r in segmentos) != {
            (a, b, tipo) for a, b in pares for tipo in tipos
        }:
            raise DadosInconsistentes("Segmentos da Etapa 4 não correspondem às transições")
        if set((r.get("data_anterior"), r.get("data_atual")) for r in indicadores) != set(pares):
            raise DadosInconsistentes("Indicadores da Etapa 4 não correspondem às transições")
        if any(int(meta.get(k, -1)) != n for k, n in (
            ("datas", len(datas)), ("pontos", len(pontos)),
            ("segmentos", len(segmentos)), ("transicoes", len(pares)),
        )):
            raise DadosInconsistentes("Resumo e tabelas da Etapa 4 divergem")

        return {
            "disponivel": True,
            "pontos": sorted(pontos, key=lambda r: (r["data"], r["ponto"])),
            "segmentos": sorted(segmentos, key=lambda r: (r["data_anterior"], r["ponto"])),
            "indicadores": sorted(indicadores, key=lambda r: r["data_anterior"]),
        }

    def camada(self, incendio: int, dia: str,
               layer: str) -> tuple[Path, dict]:
        validar_data(dia)
        arquivos = self._obrigatorios(incendio)
        r5, _ = self._resumos(arquivos, incendio)
        indice, manifesto = IndiceGeoJSON(
            arquivos["raiz"]
        ).obter(
            layer, arquivos[layer], incendio,
            esperado_sha=r5.get(f"sha256_{layer}"),
        )
        if dia not in manifesto["datas"]:
            raise EventoNaoEncontrado(
                f"Data {dia} não encontrada para {layer.upper()}"
            )
        return indice, manifesto

    def dia(self, incendio: int, dia: str) -> dict:
        validar_data(dia)
        meta = self.resumo(incendio)
        if dia not in meta["datas"]:
            raise EventoNaoEncontrado("Data não consta no evento")
        linha = next(
            (r for r in self.series(incendio) if r["data"] == dia), None
        )
        transicao = next(
            (r for r in self.transicoes(incendio)
             if r["data_atual"] == dia), None
        )
        return {
            "data": dia, "metricas": linha, "transicao": transicao,
        }
