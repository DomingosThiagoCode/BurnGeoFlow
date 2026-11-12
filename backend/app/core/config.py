"""Configuração da API local, sem login remoto nem credenciais armazenadas."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def caminho_dados() -> Path:
    caminho = os.environ.get("BURNGEOFLOW_DATA_DIR")
    return Path(caminho).expanduser().resolve() if caminho else ROOT / "execucoes"


def origens_permitidas() -> list[str]:
    valor = os.environ.get("BURNGEOFLOW_CORS_ORIGINS")
    if valor is None:
        if os.environ.get("BURNGEOFLOW_ENV", "development") == "production":
            return []
        return ["http://localhost:5173", "http://127.0.0.1:5173"]
    return [x.strip() for x in valor.split(",") if x.strip()]
