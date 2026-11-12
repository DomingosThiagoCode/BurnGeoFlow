"""API REST somente leitura do BurnGeoFlow, desacoplada da computação GEE."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Literal
import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, StreamingResponse

from backend.app.core.errors import EventoNaoEncontrado
from backend.app.repositories.eventos import RepositorioEventos
from backend.app.repositories.geojson_index import IndiceGeoJSON

logger = logging.getLogger("burngeoflow.api")
router = APIRouter(prefix="/api", tags=["eventos"])


def repo(request: Request) -> RepositorioEventos:
    return request.app.state.repositorio


@router.get("/health")
def health():
    return {"status": "ok", "service": "burngeoflow-api", "read_only": True}


@router.get("/events")
def eventos(r: RepositorioEventos = Depends(repo)):
    return [{"id_incendio": n} for n in r.listar()]


@router.get("/events/{incendio}/overview")
def resumo(incendio: int, r: RepositorioEventos = Depends(repo)):
    return r.resumo(incendio)


@router.get("/events/{incendio}/series")
def serie(incendio: int, r: RepositorioEventos = Depends(repo)):
    return r.series(incendio)


@router.get("/events/{incendio}/transitions")
def transicoes(incendio: int, r: RepositorioEventos = Depends(repo)):
    return r.transicoes(incendio)


@router.get("/events/{incendio}/dates/{dia}")
def dados_data(incendio: int, dia: str, r: RepositorioEventos = Depends(repo)):
    return r.dia(incendio, dia)


@router.get("/events/{incendio}/dates/{dia}/geometry")
def geometria(
    incendio: int,
    dia: str,
    layer: Literal["p1", "p2"] = Query(default="p1"),
    r: RepositorioEventos = Depends(repo),
):
    pasta, manifesto = r.camada(incendio, dia, layer)
    etag = '"' + sha256(
        f"{manifesto['sha256']}:{layer}:{dia}".encode("ascii")
    ).hexdigest() + '"'
    return StreamingResponse(
        IndiceGeoJSON.iterar_geojson(pasta, dia),
        media_type="application/geo+json",
        headers={"ETag": etag, "Cache-Control": "private, no-cache"},
    )


@router.get("/events/{incendio}/downloads/series.csv")
def baixar_serie(incendio: int, r: RepositorioEventos = Depends(repo)):
    # Verifica proveniência, ID e disponibilidade antes de devolver o arquivo.
    if not r.series(incendio):
        raise EventoNaoEncontrado("Série temporal ainda indisponível")
    caminho = r.arquivos(incendio)["serie"]
    return FileResponse(
        caminho, media_type="text/csv",
        filename=f"BurnGeoFlow_{incendio}_serie.csv",
    )
