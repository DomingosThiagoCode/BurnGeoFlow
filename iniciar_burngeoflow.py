"""Inicializa a versão compilada do BurnGeoFlow com um único servidor local.

Primeiro uso:
    python -m pip install -r requirements-api.txt
    cd frontend
    npm ci
    npm run build
    cd ..
Uso cotidiano:
    python iniciar_burngeoflow.py

Não executa o GEE por conta própria; jobs exigem ação explícita no painel.
"""
from __future__ import annotations

import argparse

from backend.app.core.config import ROOT


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--porta", type=int, default=8000)
    argumentos = ap.parse_args(argv)
    if not (1 <= argumentos.porta <= 65535):
        ap.error("A porta deve estar entre 1 e 65535")
    dist = ROOT / "frontend" / "dist" / "index.html"
    if not dist.is_file():
        ap.exit(
            2,
            "[ERRO] Frontend compilado ausente. Execute uma vez:\n"
            "  cd frontend\n"
            "  npm ci\n"
            "  npm run build\n"
            "  cd ..\n",
        )

    import uvicorn

    print(
        "BurnGeoFlow disponível em http://127.0.0.1:"
        + str(argumentos.porta), flush=True,
    )
    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=argumentos.porta,
        workers=1,
        reload=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
