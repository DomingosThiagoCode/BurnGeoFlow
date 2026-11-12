"""Persistência operacional SQLite dos jobs, independente dos GeoJSONs.

Não armazena geometria nem modifica as tabelas científicas. O banco é novo,
reconstruível apenas quanto aos metadados de execução, não quanto ao estado de
uma tarefa em andamento. Migrações futuras exigirão backup explícito.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

ESTADOS_ATIVOS = ("queued", "running")
ESTADOS_FINAIS = ("completed", "failed", "interrupted")


class JobConflito(RuntimeError):
    """Outra tarefa está em execução ou transição inválida."""


class JobNaoEncontrado(LookupError):
    """ID de job desconhecido."""


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value)


def vivo(pid: int | None) -> bool:
    if not pid or pid < 1:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        # Windows pode não permitir verificação estável via kill(pid,0).
        # Desconhecido deve ser tratado como vivo: não declarar falha falsa.
        return True


class JobStore:
    def __init__(self, db: Path):
        self.db = Path(db).expanduser().resolve()
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self._inicializar()

    def conexao(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db, timeout=10, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=10000")
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def _inicializar(self) -> None:
        with self.conexao() as c:
            versao = c.execute("PRAGMA user_version").fetchone()[0]
            if versao > 1:
                raise RuntimeError("Schema SQLite desconhecido: atualização necessária")
            if versao == 0:
                nomes = {
                    r[0] for r in c.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if "jobs" in nomes:
                    raise RuntimeError(
                        "SQLite existente sem versão de schema: não migrar automaticamente"
                    )
                c.execute("BEGIN IMMEDIATE")
                try:
                    c.execute("""
                        CREATE TABLE IF NOT EXISTS jobs (
                          id TEXT PRIMARY KEY,
                          incendio INTEGER NOT NULL CHECK (incendio > 0),
                          origem TEXT NOT NULL
                            CHECK (origem IN ('auto','local','gee','brutos')),
                          ano INTEGER CHECK (ano BETWEEN 2001 AND 2020),
                          status TEXT NOT NULL
                            CHECK (status IN (
                              'queued','running','completed','failed','interrupted'
                            )),
                          pid INTEGER,
                          created_at TEXT NOT NULL,
                          started_at TEXT,
                          finished_at TEXT,
                          heartbeat_at TEXT,
                          exit_code INTEGER,
                          error TEXT
                        )
                    """)
                    # Impede concorrência pesada em um servidor geoespacial
                    # local, inclusive se houver duas requisições simultâneas.
                    c.execute("""
                        CREATE UNIQUE INDEX IF NOT EXISTS ix_jobs_single_active
                        ON jobs ((1))
                        WHERE status IN ('queued','running')
                    """)
                    c.execute("PRAGMA user_version=1")
                    c.execute("COMMIT")
                except Exception:
                    c.execute("ROLLBACK")
                    raise
            c.execute("PRAGMA journal_mode=WAL")

    @staticmethod
    def _obj(row: sqlite3.Row | None) -> dict | None:
        return dict(row) if row is not None else None

    def criar(self, incendio: int, origem: str, ano: int | None) -> dict:
        identificador = uuid4().hex
        with self.conexao() as c:
            try:
                c.execute(
                    """INSERT INTO jobs
                       (id, incendio, origem, ano, status, created_at)
                       VALUES (?, ?, ?, ?, 'queued', ?)""",
                    (identificador, incendio, origem, ano, utc()),
                )
            except sqlite3.IntegrityError as exc:
                raise JobConflito(
                    "Uma execução já está aguardando ou rodando. "
                    "Aguarde a conclusão antes de iniciar outra."
                ) from exc
        return self.obter(identificador)

    def obter(self, job_id: str) -> dict:
        with self.conexao() as c:
            item = self._obj(
                c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            )
        if item is None:
            raise JobNaoEncontrado("Execução desconhecida")
        return item

    def listar(self, limite: int = 20) -> list[dict]:
        with self.conexao() as c:
            return [
                dict(r) for r in c.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                    (max(1, min(limite, 100)),),
                )
            ]

    def iniciar(self, job_id: str, pid: int) -> None:
        with self.conexao() as c:
            cursor = c.execute(
                """UPDATE jobs SET status='running',
                   pid=?, started_at=?, heartbeat_at=?
                   WHERE id=? AND status='queued'""",
                (pid, utc(), utc(), job_id),
            )
            if cursor.rowcount != 1:
                raise JobConflito("Tarefa não está na fila de execução")

    def heartbeat(self, job_id: str) -> None:
        with self.conexao() as c:
            c.execute(
                """UPDATE jobs SET heartbeat_at=?
                   WHERE id=? AND status='running'""",
                (utc(), job_id),
            )

    def finalizar(
        self, job_id: str, exit_code: int,
        erro: str | None = None,
    ) -> None:
        estado = "completed" if exit_code == 0 else "failed"
        with self.conexao() as c:
            cursor = c.execute(
                """UPDATE jobs SET status=?, exit_code=?, error=?,
                   heartbeat_at=?, finished_at=?
                   WHERE id=? AND status IN ('queued','running')""",
                (estado, exit_code, erro, utc(), utc(), job_id),
            )
            if cursor.rowcount != 1:
                raise JobConflito("Tarefa já finalizada")

    def reconciliar(self, job: dict, *, timeout_s: float = 120) -> dict:
        if job["status"] not in ESTADOS_ATIVOS:
            return job
        base = job["heartbeat_at"] or job["created_at"]
        if (datetime.now(timezone.utc) - parse_utc(base)).total_seconds() < timeout_s:
            return job
        if vivo(job["pid"]):
            return job
        with self.conexao() as c:
            c.execute(
                """UPDATE jobs SET status='interrupted', error=?,
                   finished_at=?
                   WHERE id=? AND status IN ('queued','running')
                   AND heartbeat_at IS ?""",
                ("Processo não atualiza estado e não está ativo", utc(),
                 job["id"], job["heartbeat_at"]),
            )
        return self.obter(job["id"])
