"""Worker independente do processo web: executa a CLI e registra resultado.

O servidor FastAPI não bloqueia enquanto o subprocesso GEE roda. Não
importa Streamlit nem duplica métodos geoespaciais. A execução pode
sobreviver ao encerramento do processo do servidor.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
from threading import Event, Thread

from backend.app.core.config import ROOT
from backend.app.repositories.jobs import JobStore


def trabalhar(database: Path, base: Path, job_id: str) -> int:
    store = JobStore(database)
    job = store.obter(job_id)
    store.iniciar(job_id, os.getpid())
    logs = base / ".burngeoflow" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / (job_id + ".log")

    comando = [
        sys.executable, str(ROOT / "executar_pipeline.py"),
        "--id", str(job["incendio"]),
        "--origem", job["origem"],
        "--saida", str(base / str(job["incendio"])),
    ]
    if job["ano"] is not None:
        comando.extend(["--ano", str(job["ano"])])
    parar = Event()

    def atualizar() -> None:
        while not parar.wait(5):
            try:
                store.heartbeat(job_id)
            except OSError:
                # Falha transitória de disco não deve interromper GEE.
                pass

    thread = Thread(target=atualizar, daemon=True)
    thread.start()
    codigo = 1
    erro = None
    try:
        with log_path.open("a", encoding="utf-8", buffering=1) as log:
            log.write(
                "[JOB] " + job_id + " | ID " + str(job["incendio"]) +
                " | origem " + job["origem"] + "\n"
            )
            processo = subprocess.Popen(
                comando, cwd=ROOT, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED":"1"},
                close_fds=True,
            )
            codigo = processo.wait()
            log.write("\n[JOB] Encerrado: código " + str(codigo) + "\n")
    except (OSError, ValueError) as exc:
        erro = f"{type(exc).__name__}: {exc}"
        with log_path.open("a", encoding="utf-8") as log:
            log.write("[JOB] ERRO: " + erro + "\n")
    finally:
        parar.set()
        thread.join(timeout=2)
        store.finalizar(job_id, codigo, erro)
    return codigo


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--database", type=Path, required=True)
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--id", type=str, required=True)
    args = ap.parse_args()
    try:
        return trabalhar(args.database, args.base, args.id)
    except Exception as exc:
        # Worker não expõe os detalhes da exceção na API pública.
        print(f"[JOB] Falha crítica: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
