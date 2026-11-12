"""Operações locais: execução segura por ID, com estado persistido."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.core.config import origens_permitidas
from backend.app.repositories.jobs import JobConflito, JobNaoEncontrado
from backend.app.schemas.jobs import Execucao, LogsExecucao, NovaExecucao
from backend.app.services.job_service import JobService

logger = logging.getLogger("burngeoflow.jobs")
router = APIRouter(prefix="/api/jobs", tags=["execucoes"])


def servico(request: Request) -> JobService:
    if not hasattr(request.app.state, "job_service"):
        base = request.app.state.repositorio.base
        request.app.state.job_service = JobService(base)
    return request.app.state.job_service


def verificacao_mutacao(request: Request):
    # CORS não é autenticação. O serviço de jobs só aceita POST de
    # origem localhost previamente autorizada (ou cliente CLI sem Origin).
    host = request.url.hostname
    if host not in ("127.0.0.1", "localhost", "testserver"):
        raise HTTPException(status_code=403, detail="Somente host local")
    origin = request.headers.get("Origin")
    if origin and origin not in origens_permitidas():
        raise HTTPException(status_code=403, detail="Origin não permitida")


@router.get("", response_model=list[Execucao])
def listar(serv: JobService = Depends(servico)):
    return serv.listar()


@router.post("", response_model=Execucao, status_code=202,
             dependencies=[Depends(verificacao_mutacao)])
def iniciar(req: NovaExecucao, serv: JobService = Depends(servico)):
    try:
        return serv.criar(req.id_incendio, req.origem, req.ano)
    except JobConflito as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Erro iniciando worker")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{job_id}", response_model=Execucao)
def status(job_id: str, serv: JobService = Depends(servico)):
    try:
        return serv.obter(job_id)
    except (JobNaoEncontrado, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{job_id}/logs", response_model=LogsExecucao)
def logs(job_id: str, serv: JobService = Depends(servico)):
    try:
        return serv.log(job_id, limite=100)
    except (JobNaoEncontrado, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
