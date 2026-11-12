"""App factory FastAPI. Iniciar em loopback:

python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.routes import router
from backend.app.api.jobs import router as jobs_router
from backend.app.core.config import caminho_dados, origens_permitidas
from backend.app.core.errors import (
    DadosInconsistentes, EntradaInvalida, EventoNaoEncontrado,
)
from backend.app.repositories.eventos import RepositorioEventos

logger = logging.getLogger("burngeoflow.api")


def criar_app(*, dados_dir: Path | None = None) -> FastAPI:
    app = FastAPI(
        title="BurnGeoFlow API", version="0.1.0",
        description="Consulta local de resultados geoespaciais. "
        "Exibe resultados locais e pode acionar a CLI em worker isolado. "
        "Não realiza validação científica externa.",
    )
    app.state.repositorio = RepositorioEventos(dados_dir or caminho_dados())

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origens_permitidas(),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(EventoNaoEncontrado)
    async def nao_encontrado(request: Request, exc: EventoNaoEncontrado):
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": str(exc)}},
        )

    @app.exception_handler(EntradaInvalida)
    async def entrada(request: Request, exc: EntradaInvalida):
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "INVALID_INPUT", "message": str(exc)}},
        )

    @app.exception_handler(DadosInconsistentes)
    async def conflito(request: Request, exc: DadosInconsistentes):
        logger.warning("Dados inconsistentes: %s", exc)
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "DATA_CONFLICT", "message": str(exc)}},
        )

    @app.exception_handler(RequestValidationError)
    async def parametros(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": {
                "code": "INVALID_INPUT",
                "message": "Parâmetros fora do formato esperado.",
            }},
        )

    app.include_router(router)
    app.include_router(jobs_router)
    return app


app = criar_app()
