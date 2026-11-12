"""Contratos para jobs SQLite e execução local sem chamar GEE."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
import unittest

from fastapi.testclient import TestClient

from backend.app.main import criar_app
from backend.app.repositories.jobs import JobConflito, JobStore
from backend.app.services.job_service import JobService
from backend.app.jobs.worker import trabalhar


class TestJobsStore(unittest.TestCase):
    def test_uma_execucao_ativa_por_vez_e_reabertura(self):
        with TemporaryDirectory() as temp:
            banco = Path(temp) / "jobs.sqlite3"
            s = JobStore(banco)
            j = s.criar(24340828, "local", 2020)
            self.assertEqual(j["status"], "queued")
            with self.assertRaises(JobConflito):
                s.criar(24340829, "gee", None)
            s.iniciar(j["id"], 12345)
            self.assertEqual(s.obter(j["id"])["status"], "running")
            s.heartbeat(j["id"])
            s.finalizar(j["id"], 0)
            self.assertEqual(s.obter(j["id"])["exit_code"], 0)
            self.assertEqual(s.obter(j["id"])["status"], "completed")
            with self.assertRaises(JobConflito):
                s.finalizar(j["id"], 0)
            self.assertEqual(len(JobStore(banco).listar()), 1)
            self.assertEqual(s.criar(24340829, "gee", 2020)["status"], "queued")

    def test_schema_nao_migra_silenciosamente(self):
        with TemporaryDirectory() as temp:
            banco = Path(temp) / "db.sqlite3"
            s = JobStore(banco)
            with s.conexao() as c:
                c.execute("PRAGMA user_version=2")
            with self.assertRaisesRegex(RuntimeError, "desconhecido"):
                JobStore(banco)

    def test_reconciliacao_so_depois_timeout_e_pid_inexistente(self):
        with TemporaryDirectory() as temp:
            s = JobStore(Path(temp) / "db.sqlite3")
            j = s.criar(24340828, "auto", None)
            self.assertEqual(s.reconciliar(j, timeout_s=120)["status"], "queued")
            j["created_at"] = (datetime.now(timezone.utc) -
                timedelta(minutes=5)).isoformat()
            with s.conexao() as c:
                c.execute("UPDATE jobs SET created_at=? WHERE id=?",
                          (j["created_at"], j["id"]))
            with patch("backend.app.repositories.jobs.vivo", return_value=False):
                result = s.reconciliar(s.obter(j["id"]), timeout_s=120)
            self.assertEqual(result["status"], "interrupted")


class TestJobsAPI(unittest.TestCase):
    def test_criar_listar_log_e_concorrencia(self):
        with TemporaryDirectory() as temp, patch(
            "backend.app.services.job_service.subprocess.Popen"
        ) as popen:
            popen.return_value = MagicMock()
            base = Path(temp)
            with TestClient(criar_app(dados_dir=base)) as client:
                post = client.post("/api/jobs", json={
                    "id_incendio": 24340828,
                    "origem": "local",
                }, headers={"Origin":"http://localhost:5173"})
                self.assertEqual(post.status_code, 202, post.text)
                job = post.json()
                self.assertEqual(job["status"], "queued")
                self.assertEqual(job["incendio"], 24340828)
                self.assertEqual(client.get("/api/jobs").json()[0]["id"], job["id"])
                self.assertEqual(client.get("/api/jobs/"+job["id"]).status_code, 200)
                self.assertEqual(client.get("/api/jobs/"+job["id"]+"/logs").json()["lines"], [])
                concorrente = client.post("/api/jobs", json={
                    "id_incendio": 24340829, "origem": "gee",
                })
                self.assertEqual(concorrente.status_code, 409)
                self.assertEqual(
                    client.post("/api/jobs", json={
                        "id_incendio": 24340829, "origem": "gee",
                    }, headers={"Origin":"http://evil.example"}).status_code,
                    403,
                )
                self.assertEqual(
                    client.post("/api/jobs", json={
                        "id_incendio": -1, "origem": "gee",
                    }).status_code, 422
                )
                self.assertEqual(
                    client.post("/api/jobs", json={
                        "id_incendio": 24340828, "origem": "local", "ano":2020
                    }).status_code, 422
                )
                self.assertEqual(client.get("/api/jobs/invalid").status_code, 404)
                self.assertTrue(popen.called)
                args=popen.call_args.args[0]
                self.assertEqual(args[0], __import__("sys").executable)
                self.assertNotIn("shell", popen.call_args.kwargs)

    def test_worker_termina_e_loga_sem_gge(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            s = JobStore(base / ".burngeoflow" / "jobs.sqlite3")
            job = s.criar(24340828, "local", None)
            with patch("backend.app.jobs.worker.subprocess.Popen") as popen:
                popen.return_value.wait.return_value=0
                codigo = trabalhar(s.db, base, job["id"])
            self.assertEqual(codigo, 0)
            novo = JobStore(s.db).obter(job["id"])
            self.assertEqual(novo["status"], "completed")
            self.assertIsNotNone(novo["started_at"])
            self.assertIsNotNone(novo["finished_at"])
            texto = (base / ".burngeoflow" / "logs" /
                     (job["id"]+".log")).read_text(encoding="utf-8")
            self.assertIn("Encerrado: código 0", texto)
            self.assertIn("--origem", popen.call_args.args[0])
            self.assertIn("--saida", popen.call_args.args[0])
            self.assertNotIn("shell", popen.call_args.kwargs)

    def test_log_paginado_nao_acessa_arquivos_externos(self):
        with TemporaryDirectory() as temp:
            service = JobService(Path(temp))
            job = service.store.criar(24340828, "local", None)
            log = service.work / "logs" / (job["id"]+".log")
            log.parent.mkdir(parents=True)
            log.write_text("\n".join(f"linha {i}" for i in range(500)),
                           encoding="utf-8")
            linhas=service.log(job["id"], limite=15)
            self.assertEqual(len(linhas["lines"]),15)
            self.assertTrue(linhas["truncated"])
            with self.assertRaises(ValueError):
                service.log("../../etc/passwd")


if __name__ == "__main__":
    unittest.main()
