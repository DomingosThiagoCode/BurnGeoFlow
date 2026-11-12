"""Casos de uso para execução local segura do CLI existente."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

from backend.app.core.config import ROOT
from backend.app.repositories.jobs import JobStore


class JobService:
    def __init__(self, base: Path):
        self.base = Path(base).expanduser().resolve()
        self.work = self.base / ".burngeoflow"
        self.store = JobStore(self.work / "jobs.sqlite3")

    def criar(self, incendio: int, origem: str, ano: int | None) -> dict:
        job = self.store.criar(incendio, origem, ano)
        comando = [
            sys.executable, "-m", "backend.app.jobs.worker",
            "--database", str(self.store.db), "--id", job["id"],
            "--base", str(self.base),
        ]
        try:
            subprocess.Popen(
                comando, cwd=ROOT, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True, env={**os.environ, "PYTHONUNBUFFERED": "1"},
                start_new_session=True,
            )
        except (OSError, ValueError) as exc:
            self.store.finalizar(
                job["id"], 1, f"Não foi possível iniciar worker: {type(exc).__name__}"
            )
            raise RuntimeError("Erro ao iniciar execução local") from exc
        return self.store.obter(job["id"])

    def obter(self, job_id: str) -> dict:
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise ValueError("ID de execução inválido")
        return self.store.reconciliar(self.store.obter(job_id))

    def listar(self, limite: int = 20) -> list[dict]:
        return [
            self.store.reconciliar(j) for j in self.store.listar(limite)
        ]

    def log(self, job_id: str, limite: int = 100) -> dict:
        job = self.obter(job_id)
        destino = self.work / "logs" / (job["id"] + ".log")
        if not destino.is_file():
            return {"job_id": job_id, "lines": [], "truncated": False}
        limite = max(1, min(limite, 200))
        max_bytes = 65536
        with destino.open("rb") as f:
            f.seek(0, 2)
            n = f.tell()
            inicio = max(0, n-max_bytes)
            f.seek(inicio)
            bruto = f.read(max_bytes)
        if inicio:
            # Remove linha parcial na borda esquerda do buffer.
            bruto = bruto.partition(b"\n")[2]
        linhas = bruto.decode("utf-8", errors="replace").splitlines()
        return {
            "job_id": job_id,
            "lines": linhas[-limite:],
            "truncated": bool(inicio) or len(linhas)>limite,
        }
