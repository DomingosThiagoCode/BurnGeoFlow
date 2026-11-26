"""Contrato estrutural do validador com os GeoJSONs emitidos pela v2."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shapely.geometry import box, mapping

from burngeoflow.processamento.metodologia_v2 import VERSAO, reconstruir
from burngeoflow.validacao.produtos import verificar


class TestValidacaoProdutosV2(unittest.TestCase):
    def setUp(self):
        pasta = Path(self.enterContext(TemporaryDirectory()))
        origem = pasta / "p1.geojson"
        feicoes = [
            {
                "type": "Feature",
                "properties": {"data": dia, "rank": 1, "id_incendio": 99},
                "geometry": mapping(geometria),
            }
            for dia, geometria in [
                ("2020-01-01", box(0, 0, 1, 1)),
                ("2020-01-03", box(3, 3, 5, 5)),
                ("2020-01-04", box(3.5, 3.5, 4.5, 4.5)),
            ]
        ]
        origem.write_text(
            json.dumps({"type": "FeatureCollection", "features": feicoes}),
            encoding="utf-8",
        )
        derivados = pasta / "derivados"
        reconstruir(origem, derivados)
        self.p1 = derivados / VERSAO / "P1_componentes_99.geojson"
        self.p2 = derivados / VERSAO / "P2_regiao_movel_99.geojson"

    def editar_prop_p2(self, indice, **campos):
        geojson = json.loads(self.p2.read_text(encoding="utf-8"))
        geojson["features"][indice]["properties"].update(campos)
        self.p2.write_text(json.dumps(geojson), encoding="utf-8")

    def test_aceita_inicio_proprio_e_deltas_assinados_somente_em_v2(self):
        resultado = verificar(self.p1, self.p2, metodologia_v2=True)
        self.assertEqual(resultado["metodologia"], VERSAO)
        self.assertEqual(resultado["datas_p1"], 3)
        self.assertEqual(resultado["datas_p2"], 2)
        self.assertEqual(resultado["inicio"], "2020-01-01")
        self.assertEqual(resultado["inicio_p2"], "2020-01-03")
        self.assertEqual(
            resultado["lacunas_temporais"],
            [{"de": "2020-01-01", "ate": "2020-01-03", "dias": 2}],
        )
        reducao, = resultado["reducoes_area_nas_transicoes_p2"]
        self.assertEqual((reducao["de"], reducao["ate"]), ("2020-01-03", "2020-01-04"))
        self.assertLess(reducao["delta_area_km2"], 0.0)
        with self.assertRaisesRegex(ValueError, "não possuem as mesmas datas"):
            verificar(self.p1, self.p2)

    def test_rejeita_lacuna_entre_observacoes_p2(self):
        self.editar_prop_p2(0, data="2020-01-01")
        with self.assertRaisesRegex(ValueError, "sufixo"):
            verificar(self.p1, self.p2, metodologia_v2=True)

    def test_rejeita_primeiro_delta_calculado_contra_data_sem_p2(self):
        self.editar_prop_p2(0, delta_area_total_km2=2.0)
        with self.assertRaisesRegex(ValueError, "delta_area_total_km2 inconsistente"):
            verificar(self.p1, self.p2, metodologia_v2=True)

    def test_rejeita_delta_assinado_incorreto(self):
        self.editar_prop_p2(1, delta_area_km2=0.0)
        with self.assertRaisesRegex(ValueError, "delta_area_km2 inconsistente"):
            verificar(self.p1, self.p2, metodologia_v2=True)

    def test_rejeita_representatividade_inconsistente(self):
        self.editar_prop_p2(0, representatividade_pct=42.0)
        with self.assertRaisesRegex(ValueError, "representatividade"):
            verificar(self.p1, self.p2, metodologia_v2=True)

    def test_rejeita_versao_divergente(self):
        self.editar_prop_p2(0, metodologia="v2-incorreta")
        with self.assertRaisesRegex(ValueError, "versão de metodologia"):
            verificar(self.p1, self.p2, metodologia_v2=True)
