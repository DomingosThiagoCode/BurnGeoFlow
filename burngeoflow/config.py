"""Configuração do GEE sem credenciais versionadas."""
from __future__ import annotations
from dataclasses import dataclass
import os
from pathlib import Path

class ErroConfiguracao(ValueError):
    pass

@dataclass(frozen=True)
class ConfiguracaoGEE:
    projeto: str
    modo: str = "oauth"

def carregar_configuracao_gee(*, projeto: str | None = None, arquivo_env: Path | None = None) -> ConfiguracaoGEE:
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise ErroConfiguracao("Instale requirements-gee.txt para carregar .env.") from exc
    if arquivo_env is None:
        arquivo_env = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(dotenv_path=arquivo_env, override=False)
    nome = (projeto or os.environ.get("EE_PROJECT_ID", "")).strip()
    modo = os.environ.get("EE_AUTH_MODE", "oauth").strip().lower()
    if not nome:
        raise ErroConfiguracao("Defina EE_PROJECT_ID no .env ou no ambiente.")
    if modo != "oauth":
        raise ErroConfiguracao("A versão atual suporta OAuth local.")
    return ConfiguracaoGEE(projeto=nome, modo=modo)
