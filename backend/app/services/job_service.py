"""Casos de uso para execução local segura do CLI existente."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Lock
import psutil

from backend.app.core.config import ROOT
from backend.app.repositories.jobs import JobStore, JobConflito, parse_utc
from datetime import datetime, timezone

_CANCEL_LOCK = Lock()


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
                start_new_session=(os.name != "nt"),
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    if os.name == "nt" else 0
                ),
            )
        except (OSError, ValueError) as exc:
            self.store.finalizar(
                job["id"], 1, f"Não foi possível iniciar worker: {type(exc).__name__}"
            )
            raise RuntimeError("Erro ao iniciar execução local") from exc
        return self.store.obter(job["id"])

    def _orfaos(self, job: dict) -> list:
        """Descendentes sem worker: só processos do mesmo evento e checkout."""
        destino = os.path.normcase(str(self.base / str(job["incendio"])))
        script = os.path.normcase(str(ROOT / "executar_pipeline.py"))
        inicio = parse_utc(job["started_at"] or job["created_at"]).timestamp()
        encontrados = []
        for p in psutil.process_iter(["cmdline", "create_time"]):
            try:
                args = p.info["cmdline"] or []
                if not args or (p.info["create_time"] or 0) < inicio - 2:
                    continue
                normal = [os.path.normcase(a) for a in args]
                cli = script in normal and destino in normal
                etapa = any(a.startswith("burngeoflow.") for a in args) and any(
                    a == destino or a.startswith(destino + os.sep) for a in normal)
                if cli or etapa:
                    encontrados.append(p)
            except psutil.NoSuchProcess:
                continue
        return encontrados

    def _reconciliar(self, job: dict) -> dict:
        if job["status"] == "running":
            ultima = parse_utc(job["heartbeat_at"] or job["created_at"])
            if (datetime.now(timezone.utc) - ultima).total_seconds() >= 120:
                try:
                    proc = psutil.Process(job["pid"])
                    args = proc.cmdline()
                    if job["id"] in args and "backend.app.jobs.worker" in args:
                        return job
                except psutil.AccessDenied:
                    return job
                except psutil.NoSuchProcess:
                    pass
                if self._orfaos(job):
                    return job
                return self.store.interromper(job["id"], "running", job["pid"])
        return self.store.reconciliar(job)

    def obter(self, job_id: str) -> dict:
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise ValueError("ID de execução inválido")
        return self._reconciliar(self.store.obter(job_id))

    def listar(self, limite: int = 20) -> list[dict]:
        return [
            self._reconciliar(j) for j in self.store.listar(limite)
        ]

    def interromper(self, job_id: str) -> dict:
        with _CANCEL_LOCK:
            job = self.obter(job_id)
            if job["status"] == "queued":
                job = self.store.interromper(job_id, "queued", None)
            if job["status"] != "running":
                return job
            # Nunca sinalizar um PID arbitrário ou reciclado.
            try:
                proc = None
                try:
                    candidato = psutil.Process(job["pid"])
                    args = candidato.cmdline()
                except psutil.NoSuchProcess:
                    args = []
                if ("backend.app.jobs.worker" not in args or "--id" not in args
                    or args[args.index("--id")+1:args.index("--id")+2] != [job_id]
                    or "--database" not in args
                    or args[args.index("--database")+1:args.index("--database")+2] != [str(self.store.db)]):
                    raizes = self._orfaos(job)
                else:
                    proc = candidato
                    raizes = [proc]
                if not raizes:
                    return self.store.interromper(job_id, "running", job["pid"])
                # Congela o worker antes de capturar a árvore de descendentes.
                suspensos = []
                try:
                    for raiz in raizes:
                        try:
                            raiz.suspend()
                            suspensos.append(raiz)
                        except psutil.NoSuchProcess:
                            continue
                    # Suspender pais antes de inspecionar seus filhos impede novos
                    # subprocessos durante a coleta.
                    fila = list(suspensos)
                    while fila:
                        pai = fila.pop()
                        for filho in pai.children():
                            if filho in suspensos:
                                continue
                            try:
                                filho.suspend()
                                suspensos.append(filho)
                                fila.append(filho)
                            except psutil.NoSuchProcess:
                                continue
                    for alvo in reversed(suspensos):
                        try:
                            alvo.kill()
                        except psutil.NoSuchProcess:
                            pass
                    _, vivos = psutil.wait_procs(suspensos, timeout=5)
                    if vivos:
                        raise JobConflito("Não foi possível confirmar o fim de todos os processos.")
                finally:
                    for alvo in reversed(suspensos):
                        try:
                            if alvo.is_running() and alvo.status() != psutil.STATUS_ZOMBIE:
                                alvo.resume()
                        except psutil.Error:
                            pass
            except psutil.NoSuchProcess as exc:
                if not self._orfaos(job):
                    return self.store.interromper(job_id, "running", job["pid"])
                raise JobConflito("Ainda há subprocessos; tente interromper novamente.") from exc
            except psutil.Error as exc:
                raise JobConflito(f"Não foi possível interromper com segurança: {exc}") from exc
            return self.store.interromper(job_id, "running", job["pid"])

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
