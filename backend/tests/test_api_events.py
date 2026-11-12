"""Contrato FastAPI e repositório por data, sem chamadas GEE."""
from __future__ import annotations

import csv
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from backend.app.main import criar_app
from backend.app.repositories.geojson_index import IndiceGeoJSON

ID = 24340828
DATAS = ("2020-09-10", "2020-09-11", "2020-09-12")


def dados_teste(raiz: Path, *, resumido=True):
    base = raiz / str(ID)
    pasta = base / "dados" / f"estudo_caso_{ID}"
    pasta.mkdir(parents=True)
    saidas = base / "resultados" / "etapa5"
    saidas.mkdir(parents=True)
    features_p1 = []
    features_p2 = []
    for i, dia in enumerate(DATAS):
        for rank in (1, 2):
            x = -56 + rank * .01 + i * .001
            feat = {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[
                    [x, -17], [x + .005, -17],
                    [x + .005, -16.995], [x, -16.995], [x, -17],
                ]]},
                "properties": {
                    "data": dia, "id_incendio": ID, "rank": rank,
                },
            }
            features_p1.append(feat)
            if rank == 1:
                features_p2.append({
                    **feat,
                    "properties": {
                        "data": dia, "id_incendio": ID,
                        "rank_global": 1,
                    },
                })
    for nome, dados in (("P1_componentes", features_p1),
                        ("P2_regiao_movel", features_p2)):
        (pasta / f"{nome}_{ID}.geojson").write_text(
            json.dumps({
                "type": "FeatureCollection", "features": dados,
            }), encoding="utf-8",
        )
    if not resumido:
        return pasta
    series = [{
        "data": dia, "id_incendio": ID,
        "area_total_laea_km2": 30 + i,
        "p2_area_laea_km2": 15+i,
        "numero_patches": 2,
    } for i, dia in enumerate(DATAS)]
    transicoes = [{
        "data_anterior": a, "data_atual": b,
        "dias_intervalo": 1, "id_incendio": ID,
        "eventos_convergencia": 0,
    } for a, b in zip(DATAS, DATAS[1:])]
    for nome, rows in (("serie_diaria_integrada", series),
                       ("transicoes_integradas", transicoes)):
        with (saidas / f"{nome}_{ID}.csv").open(
            "w", newline="", encoding="utf-8",
        ) as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    (saidas / f"resumo_etapa5_{ID}.json").write_text(
        json.dumps({
            "id_incendio": ID,
            "sha256_p1": sha256(
                (pasta / f"P1_componentes_{ID}.geojson").read_bytes()
            ).hexdigest(),
            "sha256_p2": sha256(
                (pasta / f"P2_regiao_movel_{ID}.geojson").read_bytes()
            ).hexdigest(),
        }), encoding="utf-8",
    )
    etapa6 = base / "resultados" / "etapa6"
    etapa6.mkdir(parents=True)
    (etapa6 / f"resumo_validacao_{ID}.json").write_text(
        json.dumps({
            "id_incendio": ID,
            "status_cientifico": "revisao_geometrica_pendente",
            "validacao_externa_concluida": False,
            "dias_sobreposicao_p1_acima_1m2": ["2020-09-11"],
        }), encoding="utf-8",
    )
    return pasta


class TesteAPI(unittest.TestCase):
    def test_catalogo_overview_camadas_e_serie(self):
        with TemporaryDirectory() as d:
            raiz = Path(d)
            pasta = dados_teste(raiz)
            with TestClient(criar_app(dados_dir=raiz)) as c:
                self.assertEqual(c.get("/api/health").json()["status"], "ok")
                self.assertEqual(c.get("/api/events").json(), [
                    {"id_incendio": ID},
                ])
                overview = c.get(f"/api/events/{ID}/overview")
                self.assertEqual(overview.status_code, 200)
                meta = overview.json()
                self.assertEqual(meta["datas"], list(DATAS))
                self.assertEqual(meta["status_cientifico"], "revisao_geometrica_pendente")
                self.assertFalse(meta["validacao_externa_concluida"])
                self.assertEqual(len(c.get(f"/api/events/{ID}/series").json()), 3)
                self.assertEqual(len(c.get(f"/api/events/{ID}/transitions").json()), 2)
                resposta = c.get(
                    f"/api/events/{ID}/dates/2020-09-11/geometry?layer=p1"
                )
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.json()["type"], "FeatureCollection")
                self.assertEqual(len(resposta.json()["features"]), 2)
                self.assertIn("ETag", resposta.headers)
                r2 = c.get(
                    f"/api/events/{ID}/dates/2020-09-11/geometry?layer=p2"
                )
                self.assertEqual(len(r2.json()["features"]), 1)
                self.assertEqual(
                    r2.json()["features"][0]["properties"]["rank_global"], 1
                )
                resp = c.get(f"/api/events/{ID}/dates/2020-09-11")
                self.assertEqual(resp.json()["transicao"]["data_anterior"],
                                 "2020-09-10")
                baixado = c.get(f"/api/events/{ID}/downloads/series.csv")
                self.assertEqual(baixado.status_code, 200)
                self.assertIn("area_total_laea_km2", baixado.text)
                indice = raiz / str(ID) / ".visualizador_index"
                self.assertEqual(
                    len([x for x in indice.iterdir() if x.is_dir()]), 2
                )
                self.assertEqual(
                    c.get(f"/api/events/{ID}/dates/2020-09-11/geometry?layer=p1").json(),
                    resposta.json(),
                )
            # P1/P2 não podem ser modificados por consultas
            self.assertEqual(
                c.get(f"/api/events/{ID}/overview").status_code, 200
            )
            self.assertTrue((pasta / f"P1_componentes_{ID}.geojson").is_file())

    def test_404_422_e_origins(self):
        with TemporaryDirectory() as d:
            raiz = Path(d)
            dados_teste(raiz)
            with TestClient(criar_app(dados_dir=raiz)) as c:
                self.assertEqual(c.get("/api/events/999/overview").status_code, 404)
                self.assertEqual(
                    c.get(f"/api/events/{ID}/dates/2020-02-30").status_code, 422
                )
                self.assertEqual(
                    c.get(f"/api/events/{ID}/dates/2020-09-20").status_code, 404
                )
                self.assertEqual(
                    c.get(f"/api/events/{ID}/dates/2020-09-11/geometry?layer=x").status_code, 422
                )
                self.assertEqual(
                    c.get("/api/health", headers={
                        "Origin": "http://localhost:5173",
                    }).headers.get("access-control-allow-origin"),
                    "http://localhost:5173",
                )
                self.assertIsNone(
                    c.get("/api/health", headers={
                        "Origin": "https://example.com",
                    }).headers.get("access-control-allow-origin")
                )

    def test_integridade_sha_bloqueia_metricas_desatualizadas(self):
        with TemporaryDirectory() as d:
            raiz = Path(d)
            pasta = dados_teste(raiz)
            app = criar_app(dados_dir=raiz)
            with TestClient(app) as c:
                self.assertEqual(c.get(f"/api/events/{ID}/overview").status_code, 200)
                original = pasta / f"P1_componentes_{ID}.geojson"
                original.write_text(
                    original.read_text(encoding="utf-8") + " ",
                    encoding="utf-8",
                )
                r = c.get(f"/api/events/{ID}/overview")
                self.assertEqual(r.status_code, 409)
                self.assertEqual(r.json()["error"]["code"], "DATA_CONFLICT")

    def test_p1_p2_arquivos_preservados_e_indice_reconstruivel(self):
        with TemporaryDirectory() as d:
            raiz = Path(d)
            pasta = dados_teste(raiz, resumido=False)
            p1 = pasta / f"P1_componentes_{ID}.geojson"
            original = sha256(p1.read_bytes()).hexdigest()
            with TestClient(criar_app(dados_dir=raiz)) as c:
                meta = c.get(f"/api/events/{ID}/overview")
                self.assertEqual(meta.json()["total_datas"], 3)
                url = f"/api/events/{ID}/dates/2020-09-12/geometry"
                self.assertEqual(c.get(url).status_code, 200)
                pasta_cache = raiz / str(ID) / ".visualizador_index"
                for path in list(pasta_cache.iterdir()):
                    if path.is_dir():
                        import shutil
                        shutil.rmtree(path)
                self.assertEqual(c.get(url).status_code, 200)
            self.assertEqual(original, sha256(p1.read_bytes()).hexdigest())

    def test_input_geojson_invalido_gera_409(self):
        with TemporaryDirectory() as d:
            raiz = Path(d)
            pasta = dados_teste(raiz, resumido=False)
            p1 = pasta / f"P1_componentes_{ID}.geojson"
            dados = json.loads(p1.read_text(encoding="utf-8"))
            dados["features"][0]["geometry"]["type"] = "Point"
            p1.write_text(json.dumps(dados), encoding="utf-8")
            with TestClient(criar_app(dados_dir=raiz)) as c:
                r = c.get(
                    f"/api/events/{ID}/dates/2020-09-10/geometry?layer=p1"
                )
                self.assertEqual(r.status_code, 409)


if __name__ == "__main__":
    unittest.main()
