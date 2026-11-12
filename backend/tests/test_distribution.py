"""O front compilado e os endpoints coexistem no mesmo servidor local."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient

from backend.app.main import criar_app
from iniciar_burngeoflow import main as iniciar


class TesteDistribuicao(unittest.TestCase):
    def test_monta_frontend_e_preserva_api(self):
        with TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            dist = raiz / "dist"
            dist.mkdir()
            (dist / "index.html").write_text(
                "<!doctype html><title>BurnGeoFlow</title>", encoding="utf-8"
            )
            (dist / "assets").mkdir()
            (dist / "assets" / "app.js").write_text(
                "console.log('burngeoflow')", encoding="utf-8"
            )
            with TestClient(
                criar_app(dados_dir=raiz / "dados", frontend_dist=dist)
            ) as client:
                self.assertEqual(client.get("/").status_code, 200)
                self.assertIn("BurnGeoFlow", client.get("/").text)
                self.assertIn("burngeoflow", client.get("/assets/app.js").text)
                self.assertEqual(client.get("/api/health").json()["status"], "ok")
                self.assertEqual(client.get("/api/events").json(), [])
                with patch(
                    "backend.app.services.job_service.subprocess.Popen"
                ) as popen:
                    resp = client.post(
                        "/api/jobs", json={
                            "id_incendio": 24340828,
                            "origem": "local",
                        },
                        headers={"Origin": "http://testserver"},
                    )
                self.assertEqual(resp.status_code, 202)
                self.assertTrue(popen.called)

    def test_sem_build_serve_api_sem_erro(self):
        with TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            with TestClient(
                criar_app(dados_dir=raiz, frontend_dist=raiz / "ausente")
            ) as client:
                self.assertEqual(client.get("/").status_code, 404)
                self.assertEqual(client.get("/api/health").status_code, 200)

    def test_launcher_nao_inicia_sem_build(self):
        with patch("iniciar_burngeoflow.ROOT", Path("/__build_ausente__/")):
            with self.assertRaises(SystemExit) as erro:
                iniciar([])
        self.assertEqual(erro.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
