"""Casos analiticos e verificacoes de regressao para as trajetorias do P2."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

import pyproj
from shapely.geometry import box, mapping, Point

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analisar_regiao_movel import (  # noqa: E402
    PONTOS, analisar, distancia_direcao, executar, indicadores_poligono,
    pontos_cardeais, reproduzir_rastreamento, vertices_exteriores,
)
from calcular_metricas_paisagem import Patch, projetar_patches  # noqa: E402


def patch(dia, rank, geom, incendio=123):
    return Patch(dia, incendio, rank, geom.area/1e6, geom,
                 area_m2=geom.area, perimetro_m=geom.length)


class MetodologiaTests(unittest.TestCase):
    def test_extremos_cardinais_e_centroide_em_laea(self):
        geom = box(-57.1, -16.2, -57.0, -16.1)
        p = Patch("2020-01-01", 111, 1, 1, geom)
        projecao, n_reparos = projetar_patches([p])
        self.assertEqual(n_reparos, 0)
        crs = pyproj.CRS.from_proj4(projecao["definicao_laea_proj4"])
        tx = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        inv = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        pts = pontos_cardeais(geom, p.geometria, tx, inv)
        self.assertEqual(set(pts), set(PONTOS))
        self.assertAlmostEqual(pts["norte"][0][1], -16.1)
        self.assertAlmostEqual(pts["sul"][0][1], -16.2)
        self.assertAlmostEqual(pts["leste"][0][0], -57.)
        self.assertAlmostEqual(pts["oeste"][0][0], -57.1)
        self.assertEqual(pts["norte"][2], 2)
        self.assertTrue(p.geometria.covers(Point(pts["centroide"][1])))

    def test_vertices_exteriores_rejeita_geometria_nula(self):
        with self.assertRaisesRegex(ValueError, "poligonal"):
            vertices_exteriores(Point(1, 1))

    def test_distancias_azimutes_elipsoidais(self):
        geod = pyproj.Geod(ellps="WGS84")
        km, az = distancia_direcao(geod, (-57, -16), (-57, -15))
        self.assertTrue(110 < km < 112)
        self.assertAlmostEqual(az, 0, places=4)
        self.assertEqual(distancia_direcao(geod, (-57, -16), (-57, -16)), (0, None))

    def test_expansao_quatro_direcoes_e_jaccard(self):
        a = patch("2020-01-01", 1, box(0, 0, 1000, 1000))
        b = patch("2020-01-02", 1, box(-200, -300, 1500, 2000))
        r = indicadores_poligono(a, b, 1)
        self.assertAlmostEqual(r["avanco_norte_km"], 1)
        self.assertAlmostEqual(r["avanco_sul_km"], .3)
        self.assertAlmostEqual(r["avanco_leste_km"], .5)
        self.assertAlmostEqual(r["avanco_oeste_km"], .2)
        self.assertAlmostEqual(r["delta_amplitude_ns_km"], 1.3)
        self.assertAlmostEqual(r["delta_amplitude_lo_km"], .7)
        self.assertAlmostEqual(r["retencao_area_anterior_pct"], 100)
        self.assertAlmostEqual(r["jaccard_geometrico"], 1e6/b.geometria.area)
        self.assertFalse(r["lacuna_temporal"])

    def test_contracao_e_perda_area_nao_sao_confundidas(self):
        a = patch("2020-01-01", 1, box(0, 0, 1000, 1000))
        b = patch("2020-01-03", 1, box(0, 0, 500, 500))
        r = indicadores_poligono(a, b, 2)
        self.assertEqual(r["area_nova_p2_km2"], 0)
        self.assertAlmostEqual(r["area_perdida_p2_km2"], .75)
        self.assertAlmostEqual(r["incremento_liquido_km2"], -.75)
        self.assertEqual(r["retencao_area_anterior_pct"], 25)
        self.assertTrue(r["lacuna_temporal"])

    def test_intervalo_invalido_rejeitado(self):
        a = patch("2020-01-01", 1, box(0, 0, 1000, 1000))
        with self.assertRaisesRegex(ValueError, "positivo"):
            indicadores_poligono(a, a, 0)


class RastreamentoTests(unittest.TestCase):
    def test_continuidade_supera_rank_de_maior_area(self):
        d1 = [patch("2020-01-01", 1, box(0, 0, 100, 100)),
              patch("2020-01-01", 2, box(500, 500, 520, 520))]
        d2 = [patch("2020-01-02", 1, box(500, 500, 600, 600)),
              patch("2020-01-02", 2, box(0, 0, 105, 105))]
        rows = reproduzir_rastreamento(
            {"2020-01-01": d1, "2020-01-02": d2},
            {"2020-01-01": 1, "2020-01-02": 2})
        self.assertEqual([r["rank_reproduzido"] for r in rows], [1, 2])
        self.assertEqual(rows[1]["criterio_reproduzido"], "sobreposicao")
        self.assertTrue(all(r["confere"] for r in rows))

    def test_fallback_proximidade_sem_intersecao(self):
        d1 = [patch("2020-01-01", 1, box(0, 0, 10, 10))]
        d2 = [patch("2020-01-02", 1, box(200, 0, 210, 10)),
              patch("2020-01-02", 2, box(20, 0, 30, 10))]
        r = reproduzir_rastreamento(
            {"2020-01-01": d1, "2020-01-02": d2},
            {"2020-01-01": 1, "2020-01-02": 2})[1]
        self.assertEqual((r["rank_reproduzido"], r["criterio_reproduzido"]),
                         (2, "distancia_fallback"))
        self.assertAlmostEqual(r["distancia_minima_fallback_km"], .01)

    def test_empate_e_identificado(self):
        d1 = [patch("2020-01-01", 1, box(0, 0, 10, 10))]
        d2 = [patch("2020-01-02", 1, box(0, 0, 5, 10)),
              patch("2020-01-02", 2, box(5, 0, 10, 10))]
        r = reproduzir_rastreamento(
            {"2020-01-01": d1, "2020-01-02": d2},
            {"2020-01-01": 1, "2020-01-02": 1})[1]
        self.assertTrue(r["empate_melhor_escore"])
        self.assertEqual(r["rank_reproduzido"], 1)

    def test_datas_p1_p2_distintas_rejeitadas(self):
        with self.assertRaisesRegex(ValueError, "coincidir"):
            reproduzir_rastreamento({"2020-01-01": [patch("2020-01-01", 1,
                                       box(0, 0, 1, 1))]}, {})


class ArquivosReaisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raiz = Path(__file__).resolve().parents[1]
        cls.p1 = cls.raiz / "dados/estudo_caso_24340828/P1_componentes_24340828.geojson"
        cls.p2 = cls.raiz / "dados/estudo_caso_24340828/P2_regiao_movel_24340828.geojson"

    def test_regressao_integral_e_preservacao_original(self):
        if not self.p1.exists() or not self.p2.exists():
            self.skipTest("GeoJSON P1/P2 nao disponiveis")
        h1, h2 = sha256(self.p1.read_bytes()).hexdigest(), sha256(self.p2.read_bytes()).hexdigest()
        with TemporaryDirectory() as pasta:
            resumo = executar(self.p1, self.p2, Path(pasta))
            self.assertEqual((resumo["datas"], resumo["transicoes"]), (57, 56))
            self.assertEqual((resumo["pontos"], resumo["segmentos"]), (285, 280))
            self.assertEqual(resumo["ranks_rastreamento_conferem"], 57)
            self.assertEqual(len(resumo["ranks_rastreamento_divergentes"]), 0)
            self.assertEqual(resumo["criterios_rastreamento"]["sobreposicao"], 56)
            self.assertEqual(len(resumo["transicoes_com_lacuna"]), 3)
            self.assertEqual(resumo["abordagem_tr"],
                             "trajetorias_representativas_cinco_descritores")
            self.assertLess(resumo["maior_diferenca_simetrica_p1_p2_m2"], 1)
            self.assertEqual(len(list(Path(pasta).glob("*.csv"))), 4)
            self.assertEqual(len(json.loads((Path(pasta)/
                "cinco_trajetorias_24340828.geojson").read_text())["features"]), 5)
        self.assertEqual(sha256(self.p1.read_bytes()).hexdigest(), h1)
        self.assertEqual(sha256(self.p2.read_bytes()).hexdigest(), h2)

    def test_id_dinamico_e_geometria_invalida_rejeitada(self):
        g1, g2 = box(-57, -16, -56.99, -15.99), box(-57, -16, -56.98, -15.98)

        def f(dia, geom, area, p2=False):
            props = {"data": dia, "id_incendio": 777, "rank": 1,
                     "area_km2": area, "area_total_km2": area,
                     "numero_componentes": 1}
            if p2:
                props["rank_global"] = 1
            return {"type": "Feature", "geometry": mapping(geom),
                    "properties": props}

        p1 = {"type": "FeatureCollection", "features": [
            f("2020-01-01", g1, 1), f("2020-01-03", g2, 4)]}
        p2 = {"type": "FeatureCollection", "features": [
            f("2020-01-01", g1, 1, True), f("2020-01-03", g2, 4, True)]}
        with TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            a, b = raiz/"p1.geojson", raiz/"p2.geojson"
            a.write_text(json.dumps(p1), encoding="utf-8")
            b.write_text(json.dumps(p2), encoding="utf-8")
            resumo = executar(a, b, raiz/"saida")
            self.assertEqual(resumo["id_incendio"], 777)
            self.assertEqual((resumo["pontos"], resumo["segmentos"]), (10, 5))
            self.assertEqual(resumo["ranks_rastreamento_conferem"], 2)
            self.assertEqual(resumo["transicoes_com_lacuna"], ["2020-01-03"])
            p2["features"][1]["geometry"] = mapping(
                box(-56, -16, -55.98, -15.98))
            b.write_text(json.dumps(p2), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "geometria diverge"):
                executar(a, b, raiz/"erro")
            self.assertFalse((raiz/"erro").exists())


if __name__ == "__main__":
    unittest.main()
