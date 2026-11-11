"""Testes offline da aquisição GEE e contrato do comando --origem gee."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest

from burngeoflow.aquisicao.earth_engine import (
    ErroAquisicao, obter_geojson, publicar_geojsons, adquirir, localizar_evento,
)
from executar_pipeline import main


def exemplo(id_incendio: int = 24340828) -> tuple[dict, dict]:
    geometria = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]],
    }
    p1 = {"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": geometria,
        "properties": {
            "id_incendio": id_incendio, "ano_dataset": 2020,
            "data": "2020-01-01", "rank": 1,
            "area_km2": 1.0, "numero_componentes": 1,
            "area_total_km2": 1.0
        }
    }]}
    p2 = deepcopy(p1)
    p2["features"][0]["properties"].update({
        "rank_global": 1,
        "delta_area_km2": 0,
        "delta_area_total_km2": 0,
        "metodo_continuidade": "inicial_maior_area",
    })
    return p1, p2


class TestePaginacao(unittest.TestCase):
    def test_duas_paginas_sem_perda(self):
        p1, _ = exemplo()
        f1 = p1["features"][0]
        f2 = deepcopy(f1)
        f2["properties"]["rank"] = 2
        compute = Mock(side_effect=[
            {"type": "FeatureCollection", "features": [f1], "next_page_token": "p2"},
            {"type": "FeatureCollection", "features": [f2]},
        ])
        ee = SimpleNamespace(data=SimpleNamespace(computeFeatures=compute))
        resposta = obter_geojson(ee, "expressao", pagina=1)
        self.assertEqual(len(resposta["features"]), 2)
        self.assertEqual(compute.call_args_list[1].args[0]["pageToken"], "p2")

    def test_token_repetido_falha(self):
        p1, _ = exemplo()
        resposta = {"features": p1["features"], "next_page_token": "repete"}
        ee = SimpleNamespace(data=SimpleNamespace(
            computeFeatures=Mock(return_value=resposta)))
        with self.assertRaisesRegex(ErroAquisicao, "token"):
            obter_geojson(ee, "x")

    def test_erro_da_api_e_explicito(self):
        ee = SimpleNamespace(data=SimpleNamespace(
            computeFeatures=Mock(side_effect=RuntimeError("quota"))))
        with self.assertRaisesRegex(ErroAquisicao, "quota"):
            obter_geojson(ee, "x")


class TestePublicacao(unittest.TestCase):
    def test_publica_ambos_apos_validacao(self):
        p1, p2 = exemplo()
        with TemporaryDirectory() as raiz:
            caminho1, caminho2, resumo = publicar_geojsons(
                Path(raiz), 24340828, p1, p2)
            self.assertEqual(resumo["datas"], 1)
            self.assertEqual(len(json.loads(caminho1.read_text())["features"]), 1)
            self.assertTrue(caminho2.exists())
            self.assertFalse(any(Path(raiz).glob("*.backup")))

    def test_entrada_errada_preserva_arquivos_anteriores(self):
        p1, p2 = exemplo()
        with TemporaryDirectory() as raiz:
            caminho1, caminho2, _ = publicar_geojsons(
                Path(raiz), 24340828, p1, p2)
            originais = caminho1.read_bytes(), caminho2.read_bytes()
            p2_ruim = deepcopy(p2)
            p2_ruim["features"][0]["properties"]["area_total_km2"] = 9.0
            with self.assertRaises(ErroAquisicao):
                publicar_geojsons(Path(raiz), 24340828, p1, p2_ruim)
            self.assertEqual((caminho1.read_bytes(), caminho2.read_bytes()),
                             originais)


class TesteAquisicao(unittest.TestCase):
    def test_ano_ausente_retorna_erro_sem_rede(self):
        ee = SimpleNamespace(
            FeatureCollection=lambda _: SimpleNamespace(
                filter=lambda x: SimpleNamespace(
                    size=lambda: SimpleNamespace(getInfo=lambda: 0))),
            Filter=SimpleNamespace(eq=lambda k, v: (k, v)),
        )
        with self.assertRaisesRegex(ErroAquisicao, "não encontrado"):
            localizar_evento(ee, 999, ano=2020)

    @patch("burngeoflow.aquisicao.earth_engine.obter_geojson")
    @patch("burngeoflow.aquisicao.earth_engine.construir_produtos")
    @patch("burngeoflow.aquisicao.earth_engine.localizar_evento")
    def test_adquirir_mock_sem_google(self, localizar, construir, exportar):
        p1, p2 = exemplo()
        localizar.return_value = ("evento", 2020, 947)
        construir.return_value = ("p1_expr", "p2_expr", 1)
        exportar.side_effect = [p1, p2]
        with TemporaryDirectory() as raiz:
            p1_path, p2_path, meta = adquirir(
                24340828, Path(raiz), ano=2020,
                ee_modulo=object(), informar=lambda s: None,
            )
            self.assertTrue(p1_path.exists() and p2_path.exists())
            self.assertEqual(meta["ano_dataset"], 2020)
            self.assertEqual(meta["regioes_p2"], 1)
            self.assertFalse(meta["validacao_independente"])


class TesteCLI(unittest.TestCase):
    @patch("executar_pipeline.executar")
    @patch("burngeoflow.aquisicao.earth_engine.adquirir")
    def test_modo_gee_executa_analises(self, adquirir_mock, executar_mock):
        adquirir_mock.return_value = (Path("P1.geojson"), Path("P2.geojson"), {})
        with TemporaryDirectory() as raiz:
            codigo = main([
                "--id", "24340828", "--origem", "gee", "--ano", "2020",
                "--saida", raiz
            ])
        self.assertEqual(codigo, 0)
        self.assertEqual(adquirir_mock.call_args.kwargs["ano"], 2020)
        self.assertEqual(executar_mock.call_args.kwargs["origem"],
                         "Google Earth Engine / GlobFire v2")

    @patch("executar_pipeline.executar")
    @patch("burngeoflow.aquisicao.earth_engine.adquirir")
    def test_somente_aquisicao_nao_executa_analises(self, adquirir_mock, executar_mock):
        adquirir_mock.return_value = (Path("P1.geojson"), Path("P2.geojson"),
                                      {"datas": 57})
        with TemporaryDirectory() as raiz:
            codigo = main(["--id", "24340828", "--origem", "gee",
                           "--saida", raiz, "--somente-aquisicao"])
        self.assertEqual(codigo, 0)
        executar_mock.assert_not_called()

    def test_misturar_geojson_com_gee_e_rejeitado(self):
        self.assertEqual(main(["--id", "1234", "--origem", "gee",
                               "--p1", "arquivo.geojson"]), 1)


if __name__ == "__main__":
    unittest.main()
