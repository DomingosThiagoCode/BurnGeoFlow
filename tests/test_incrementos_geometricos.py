"""Testes analiticos e regressao real para incrementos geometricos temporais."""

from __future__ import annotations

import csv
from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

import pyproj
from shapely.geometry import box, GeometryCollection, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from burngeoflow.analises.incrementos import (  # noqa: E402
    calcular_incremento, executar, partes_poligonais,
)


class CasosAnaliticos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inv = pyproj.Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
        cls.geod = pyproj.Geod(ellps="WGS84")

    def calcula_caso(self, a, b, d0="2020-01-01", d1="2020-01-02"):
        return calcular_incremento(a, b, self.inv, self.geod,
                                   evento=999, dia0=d0, dia1=d1)

    def test_crescimento_unilateral_puro(self):
        r, cs, nova = self.calcula_caso(box(0, 0, 1000, 1000), box(0, 0, 2000, 1000))
        self.assertAlmostEqual(r["area_nova_km2"], 1)
        self.assertAlmostEqual(r["area_perdida_km2"], 0)
        self.assertEqual(r["numero_componentes_incremento"], 1)
        self.assertAlmostEqual(r["fracao_maior_componente"], 1)
        self.assertTrue(75 < cs[0]["azimute_incremento_graus"] < 105)
        self.assertAlmostEqual(r["concentracao_direcional"], 1)
        self.assertAlmostEqual(nova.area, 1e6)

    def test_ilhas_em_direcoes_opostas_e_cancelamento(self):
        a = box(0, 0, 1000, 1000)
        b = a.union(box(-1000, 0, 0, 1000)).union(box(1000, 0, 2000, 1000))
        r, cs, _ = self.calcula_caso(a, b)
        self.assertEqual(len(cs), 2)
        self.assertAlmostEqual(r["area_nova_km2"], 2)
        self.assertLess(r["concentracao_direcional"], .01)
        self.assertIsNone(r["azimute_medio_ponderado_graus"])

    def test_contracao_nao_e_area_nova(self):
        r, cs, _ = self.calcula_caso(box(0, 0, 1000, 1000), box(0, 0, 500, 500))
        self.assertEqual(r["area_nova_km2"], 0)
        self.assertAlmostEqual(r["area_perdida_km2"], .75)
        self.assertEqual(cs, [])
        self.assertIsNone(r["concentracao_direcional"])

    def test_lacuna_nao_e_ignorada(self):
        r, _, _ = self.calcula_caso(box(0, 0, 100, 100), box(0, 0, 200, 100),
                            d1="2020-01-05")
        self.assertEqual(r["dias_intervalo"], 4)
        self.assertTrue(r["lacuna_temporal"])

    def test_invalidos_e_tempo_duplicado(self):
        with self.assertRaisesRegex(ValueError, "Datas"):
            self.calcula_caso(box(0, 0, 1, 1), box(0, 0, 2, 2), d1="2020-01-01")
        with self.assertRaisesRegex(ValueError, "Geometrias"):
            self.calcula_caso(Polygon(), box(0, 0, 2, 2))
        with self.assertRaisesRegex(ValueError, "Diferenca nao poligonal"):
            partes_poligonais(GeometryCollection([box(0, 0, 1, 1).boundary]))


class EstudoReal(unittest.TestCase):
    def test_regressao_independente_de_resultados_anteriores(self):
        raiz = Path(__file__).resolve().parents[1]
        p1 = raiz / "dados/estudo_caso_24340828/P1_componentes_24340828.geojson"
        p2 = raiz / "dados/estudo_caso_24340828/P2_regiao_movel_24340828.geojson"
        h1, h2 = sha256(p1.read_bytes()).hexdigest(), sha256(p2.read_bytes()).hexdigest()
        with TemporaryDirectory() as temp:
            resumo = executar(p1, p2, Path(temp))
            self.assertEqual(resumo["id_incendio"], 24340828)
            self.assertEqual(resumo["observacoes"], 57)
            self.assertEqual(resumo["transicoes"], 56)
            self.assertGreater(resumo["componentes_incremento"], 56)
            self.assertAlmostEqual(resumo["area_nova_total_km2"], 949.843488705, places=5)
            self.assertLess(resumo["area_perdida_total_km2"], .00001)
            self.assertLess(resumo["max_erro_fechamento_area_m2"], 1e-3)
            with (Path(temp) / "incrementos_temporais_24340828.csv").open() as f:
                linhas = list(csv.DictReader(f))
            self.assertEqual(len(linhas), 56)
            self.assertEqual(sum(x["lacuna_temporal"] == "True" for x in linhas), 3)
            self.assertTrue(all(0 <= float(x["concentracao_direcional"]) <= 1.000000001
                                for x in linhas if x["concentracao_direcional"]))
            # Confronto cruzado: nao usa o CSV anterior como entrada.
            # Apenas compara os resultados reprocessados a partir dos GeoJSON.
            with (raiz / "resultados/etapa4/indicadores_regiao_24340828.csv").open() as f:
                comparador = {x["data_atual"]: x for x in csv.DictReader(f)}
            self.assertEqual(len(comparador), len(linhas))
            for atual in linhas:
                ref = comparador[atual["data_atual"]]
                self.assertLess(abs(float(atual["area_nova_km2"]) -
                                    float(ref["area_nova_p2_km2"])), 1e-8)
                self.assertLess(abs(float(atual["area_perdida_km2"]) -
                                    float(ref["area_perdida_p2_km2"])), 1e-8)
        self.assertEqual((sha256(p1.read_bytes()).hexdigest(),
                          sha256(p2.read_bytes()).hexdigest()), (h1, h2))


if __name__ == "__main__":
    unittest.main()
