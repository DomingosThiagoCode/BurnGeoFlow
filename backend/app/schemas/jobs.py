"""Schemas dos jobs locais (não armazenam polígonos no SQLite)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class NovaExecucao(BaseModel):
    id_incendio: int = Field(gt=0, le=2147483647)
    origem: Literal["auto", "local", "gee", "brutos"] = "auto"
    ano: int | None = Field(default=None, ge=2001, le=2020)

    @model_validator(mode="after")
    def validar_combinacao(self):
        if self.ano is not None and self.origem in ("local", "brutos"):
            raise ValueError("Ano só faz sentido em aquisição auto/gee")
        return self


class Execucao(BaseModel):
    id: str
    incendio: int
    origem: str
    ano: int | None
    status: Literal["queued", "running", "completed", "failed", "interrupted"]
    pid: int | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    heartbeat_at: str | None
    exit_code: int | None
    error: str | None


class LogsExecucao(BaseModel):
    job_id: str
    lines: list[str]
    truncated: bool
