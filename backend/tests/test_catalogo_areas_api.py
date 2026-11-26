"""Contratos da API de catálogo sem rede, autenticação GEE ou dados científicos."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient
from backend.app.main import criar_app

AOI = {"type": "Polygon", "coordinates": [[
    [-55, -20], [-54, -20], [-54, -19], [-55, -19], [-55, -20]
]]}


class TestCatalogoAPI(unittest.TestCase):
    def test_opcoes_oficiais_sem_conexao_gee(self):
        with TemporaryDirectory() as tmp, TestClient(
            criar_app(dados_dir=Path(tmp))
        ) as client:
            r=client.get("/api/catalogo/regioes")
            self.assertEqual(r.status_code, 200, r.text)
            corpo=r.json()
            self.assertIn("Pantanal", corpo["biomas"])
            self.assertEqual(corpo["pais"], "Brasil")
            self.assertEqual(len(corpo["ufs"]), 27)
            self.assertIn({"codigo": "MS", "nome": "Mato Grosso do Sul"},
                          corpo["ufs"])

    def test_uf_brasil_desqualificados_antes_do_gee(self):
        with TemporaryDirectory() as tmp, TestClient(
            criar_app(dados_dir=Path(tmp))
        ) as client, patch(
            "backend.app.api.catalogo.resolver_uf_ou_brasil",
            return_value={"geometria":AOI, "origem":"IBGE 2024 teste"},
        ) as resolver, patch(
            "backend.app.api.catalogo.catalogo",
            return_value={
                "origem":"cache local",
                "consultado_utc":"2026-11-26T12:00:00+00:00",
                "eventos":[{"id":42,"ano":2020,"registros_na_aoi":5}],
            },
        ) as consulta:
            for regiao in ("UF:MS", "Brasil"):
                r=client.post("/api/catalogo", json={
                    "regiao":regiao,"inicio":"2020-01-01",
                    "fim":"2020-01-31","margem":15,
                }, headers={"Origin":"http://localhost:5173"})
                self.assertEqual(r.status_code,200,r.text)
                self.assertEqual(r.json()["eventos"][0]["local"],
                                 {"p1":False,"p2":False,"serie":False})
            self.assertEqual(resolver.call_count,2)
            self.assertEqual(consulta.call_count,2)
            self.assertEqual(consulta.call_args.kwargs["origem"],"IBGE 2024 teste")

    def test_filtros_invalidos_nao_consultam_o_gee(self):
        with TemporaryDirectory() as tmp, TestClient(
            criar_app(dados_dir=Path(tmp))
        ) as client, patch(
            "backend.app.api.catalogo.catalogo",
            side_effect=AssertionError("Não deve consultar o GEE"),
        ):
            for origem in ("UF:XX", "Groenlândia", "../"):
                r=client.post("/api/catalogo",json={
                    "regiao":origem,"inicio":"2020-01-01","fim":"2020-01-02",
                })
                self.assertEqual(r.status_code,422,r.text)
            r=client.post("/api/catalogo",json={
                "regiao":"Pantanal","geometria":AOI,
                "inicio":"2020-01-01","fim":"2020-01-02",
            })
            self.assertEqual(r.status_code,422,r.text)
            r=client.post("/api/catalogo",json={
                "inicio":"2020-01-01","fim":"2020-01-02",
            })
            self.assertEqual(r.status_code,422,r.text)


if __name__=="__main__":
    unittest.main()
