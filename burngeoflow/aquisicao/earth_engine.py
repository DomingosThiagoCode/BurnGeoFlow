"""Adaptador GEE. A produção automática de P1/P2 segue pendente na etapa 7.2."""
from __future__ import annotations
from typing import Any
from burngeoflow.config import ConfiguracaoGEE

BASE_GLOBFIRE = "JRC/GWIS/GlobFire/v2/DailyPerimeters"
ANO_MINIMO, ANO_MAXIMO = 2001, 2020

class ErroAquisicao(RuntimeError):
    pass

def inicializar(config: ConfiguracaoGEE, *, solicitar_login: bool = False) -> Any:
    try:
        import ee
    except ImportError as exc:
        raise ErroAquisicao("Instale requirements-gee.txt.") from exc
    try:
        if solicitar_login:
            ee.Authenticate()
        ee.Initialize(project=config.projeto)
    except Exception as exc:
        raise ErroAquisicao("Falha ao iniciar GEE. Confira EE_PROJECT_ID e autenticação.") from exc
    return ee

def selecionar_evento(ee: Any, id_incendio: int, ano: int) -> Any:
    if id_incendio <= 0:
        raise ErroAquisicao("ID deve ser positivo.")
    if not ANO_MINIMO <= ano <= ANO_MAXIMO:
        raise ErroAquisicao("GlobFire v2 DailyPerimeters: anos 2001-2020.")
    return ee.FeatureCollection(f"{BASE_GLOBFIRE}/{ano}").filter(
        ee.Filter.eq("Id", id_incendio)
    )

def consultar_evento(ee: Any, id_incendio: int, ano: int) -> tuple[Any, int]:
    evento = selecionar_evento(ee, id_incendio, ano)
    try:
        total = int(evento.size().getInfo())
    except Exception as exc:
        raise ErroAquisicao("Falha na consulta GlobFire.") from exc
    if total == 0:
        raise ErroAquisicao(f"Incêndio {id_incendio} não encontrado em {ano}.")
    return evento, total
