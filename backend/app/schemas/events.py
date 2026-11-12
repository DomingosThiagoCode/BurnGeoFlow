"""Contratos HTTP explícitos, independentes das regras científicas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class EventoListado(BaseModel):
    id_incendio: int = Field(ge=1)


class VisaoEvento(BaseModel):
    id_incendio: int = Field(ge=1)
    datas: list[str]
    periodo_inicio: str | None
    periodo_fim: str | None
    total_datas: int = Field(ge=0)
    tem_series: bool
    tem_transicoes: bool
    status_cientifico: str
    validacao_externa_concluida: bool
    dias_sobreposicao_p1_pendentes: list[str]
    observacao: str


class DataEvento(BaseModel):
    data: str
    metricas: dict[str, str | None] | None = None
    transicao: dict[str, str | None] | None = None
