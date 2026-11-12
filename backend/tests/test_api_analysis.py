"""Contract tests for the read-only scientific panels."""
from __future__ import annotations

import csv
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from backend.app.main import criar_app
from backend.tests.test_api_events import DATAS, ID, dados_teste

PONTOS = ("centroide", "norte", "sul", "leste", "oeste")


def gravar_csv(path: Path, linhas: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as arq:
        w = csv.DictWriter(arq, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)


def criar_etapa4(raiz: Path) -> Path:
    base = raiz / str(ID)
    pasta = base / "resultados" / "etapa4"
    pasta.mkdir(parents=True, exist_ok=True)
    pontos = [
        {"id_incendio": ID, "data": data, "ponto": ponto,
         "x_laea_m": 100 + i, "y_laea_m": 200 + i}
        for i, data in enumerate(DATAS) for ponto in PONTOS
    ]
    segmentos = [
        {"id_incendio": ID, "data_anterior": anterior, "data_atual": atual,
         "ponto": ponto, "distancia_geodesica_km": 1.0,
         "azimute_geodesico_graus": 45}
        for anterior, atual in zip(DATAS, DATAS[1:]) for ponto in PONTOS
    ]
    indicadores = [
        {"id_incendio": ID, "data_anterior": anterior,
         "data_atual": atual, "deslocamento_centroide_km": 1.0}
        for anterior, atual in zip(DATAS, DATAS[1:])
    ]
    for nome, rows in (
        ("pontos_representativos", pontos),
        ("segmentos_trajetorias", segmentos),
        ("indicadores_regiao", indicadores),
    ):
        gravar_csv(pasta / f"{nome}_{ID}.csv", rows)

    geometria = base / "dados" / f"estudo_caso_{ID}"
    meta = {
        "id_incendio": ID, "datas": len(DATAS),
        "transicoes": len(DATAS)-1, "pontos": len(pontos),
        "segmentos": len(segmentos),
        "sha256_p1": sha256((geometria / f"P1_componentes_{ID}.geojson").read_bytes()).hexdigest(),
        "sha256_p2": sha256((geometria / f"P2_regiao_movel_{ID}.geojson").read_bytes()).hexdigest(),
    }
    alvo = pasta / f"resumo_regiao_movel_{ID}.json"
    alvo.write_text(json.dumps(meta), encoding="utf-8")
    return alvo


class TesteAnaliseEtapa4(unittest.TestCase):
    def test_ausencia_etapa4_nao_quebra_evento(self):
        with TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            dados_teste(raiz)
            with TestClient(criar_app(dados_dir=raiz)) as api:
                resp = api.get(f"/api/events/{ID}/analysis")
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.json(), {
                    "disponivel": False, "pontos": [],
                    "segmentos": [], "indicadores": [],
                })

    def test_analise_valida_e_guardas_de_proveniencia(self):
        with TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            dados_teste(raiz)
            resumo = criar_etapa4(raiz)
            with TestClient(criar_app(dados_dir=raiz)) as api:
                resposta = api.get(f"/api/events/{ID}/analysis")
                self.assertEqual(resposta.status_code, 200)
                corpo = resposta.json()
                self.assertTrue(corpo["disponivel"])
                self.assertEqual(len(corpo["pontos"]), 15)
                self.assertEqual(len(corpo["segmentos"]), 10)
                self.assertEqual(len(corpo["indicadores"]), 2)
                self.assertEqual(corpo["pontos"][0]["data"], DATAS[0])

            meta = json.loads(resumo.read_text(encoding="utf-8"))
            meta["sha256_p2"] = "0" * 64
            resumo.write_text(json.dumps(meta), encoding="utf-8")
            with TestClient(criar_app(dados_dir=raiz)) as api:
                resposta = api.get(f"/api/events/{ID}/analysis")
                self.assertEqual(resposta.status_code, 409)
                self.assertEqual(resposta.json()["error"]["code"], "DATA_CONFLICT")

    def test_falha_para_intervalos_incompativeis(self):
        with TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            dados_teste(raiz)
            criar_etapa4(raiz)
            caminho = raiz / str(ID) / "resultados" / "etapa4" / f"segmentos_trajetorias_{ID}.csv"
            linhas = list(csv.DictReader(caminho.open(encoding="utf-8", newline="")))
            linhas[0]["data_atual"] = "2021-01-01"
            gravar_csv(caminho, linhas)
            with TestClient(criar_app(dados_dir=raiz)) as api:
                self.assertEqual(api.get(f"/api/events/{ID}/analysis").status_code, 409)


if __name__ == "__main__":
    unittest.main()
