"""Regressão offline da falha de soma de interseções (#44).

Não corrige a topologia com tolerâncias arbitrárias nem usa a rede GEE.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shapely.geometry import box, mapping

from burngeoflow.analises.paisagem import Patch
from burngeoflow.processamento.linhagens import executar, vincular_por_area
from burngeoflow.validacao.diagnostico_linhagens import (
    ExcessoIntersecoes, diagnosticar_intersecoes,
)


def patch(data: str, rank: int, geom, incendio: int = 123) -> Patch:
    p = Patch(data, incendio, rank, geom.area / 1e6, geom)
    p.area_m2, p.perimetro_m = geom.area, geom.length
    return p


class TestDiagnosticoExcesso(unittest.TestCase):
    def test_sucessores_sobrepostos_documentam_area_duplicada(self):
        anterior = patch("2020-09-10", 97, box(0, 0, 10, 10))
        # Os dois patches do dia seguinte são válidos isoladamente,
        # mas têm 60 m² sobrepostos dentro do antigo.
        seguinte = [
            patch("2020-09-11", 1, box(0, 0, 8, 10)),
            patch("2020-09-11", 2, box(2, 0, 10, 10)),
        ]
        with self.assertRaises(ExcessoIntersecoes) as ctx:
            vincular_por_area([anterior], seguinte)
        d = ctx.exception.diagnostico
        self.assertEqual((d["data_patch"], d["rank_patch"]),
                         ("2020-09-10", 97))
        self.assertEqual(d["data_oposta"], "2020-09-11")
        self.assertAlmostEqual(d["area_patch_laea_m2"], 100)
        self.assertAlmostEqual(d["soma_intersecoes_m2"], 160)
        self.assertAlmostEqual(d["uniao_intersecoes_m2"], 100)
        self.assertAlmostEqual(d["area_contada_repetidamente_m2"], 60)
        self.assertAlmostEqual(d["excesso_soma_sobre_patch_m2"], 60)
        self.assertEqual(d["numero_pares_sobrepostos"], 1)
        self.assertEqual(d["amostra_pares_sobrepostos"][0]["ranks_opostos"], [1, 2])
        self.assertTrue(d["evidencia_sobreposicao_entre_opostos"])

    def test_antecessores_sobrepostos_tambem_sao_detectados(self):
        anteriores = [
            patch("2020-09-10", 1, box(0, 0, 8, 10)),
            patch("2020-09-10", 2, box(2, 0, 10, 10)),
        ]
        atual = patch("2020-09-11", 1, box(0, 0, 10, 10))
        with self.assertRaises(ExcessoIntersecoes) as ctx:
            vincular_por_area(anteriores, [atual])
        d = ctx.exception.diagnostico
        self.assertEqual(d["lado_patch"], "atual")
        self.assertEqual(d["rank_patch"], 1)
        self.assertAlmostEqual(d["area_contada_repetidamente_m2"], 60)

    def test_disjuntas_uniao_igual_soma_e_sem_erro(self):
        antigo = patch("2020-09-10", 1, box(0, 0, 10, 10))
        novos = [
            patch("2020-09-11", 1, box(0, 0, 5, 10)),
            patch("2020-09-11", 2, box(5, 0, 10, 10)),
        ]
        arestas, *_ = vincular_por_area([antigo], novos)
        d = diagnosticar_intersecoes(antigo, novos, arestas, "anterior", 1)
        self.assertEqual(len(arestas), 2)
        self.assertAlmostEqual(d["soma_intersecoes_m2"], 100)
        self.assertAlmostEqual(d["uniao_intersecoes_m2"], 100)
        self.assertAlmostEqual(d["area_contada_repetidamente_m2"], 0)
        self.assertEqual(d["numero_pares_sobrepostos"], 0)
        self.assertFalse(d["evidencia_sobreposicao_entre_opostos"])

    def test_pequena_diferenca_numerica_nao_gera_falha(self):
        ant = patch("2020-01-01", 1, box(0, 0, 10, 10))
        ant.area_m2 -= 0.001  # bem menor que o limiar já existente de 1 m²
        nov = patch("2020-01-02", 1, box(0, 0, 10, 10))
        self.assertEqual(len(vincular_por_area([ant], [nov])[0]), 1)

    def test_persistencia_no_erro_sem_mudar_o_geojson(self):
        antigo = box(-56.0, -17.0, -55.99, -16.99)
        novo1 = box(-56.0, -17.0, -55.992, -16.99)
        novo2 = box(-55.998, -17.0, -55.99, -16.99)
        areas = {1: [100], 2: [80, 80]}
        geoms = {
            "2020-09-10": [antigo],
            "2020-09-11": [novo1, novo2],
        }
        features = []
        for data, colecao in geoms.items():
            n = len(colecao)
            for indice, geom in enumerate(colecao):
                features.append({
                    "type": "Feature",
                    "geometry": mapping(geom),
                    "properties": {
                        "id_incendio": 24194371, "data": data,
                        "rank": indice + 1,
                        "area_km2": areas[n][indice],
                        "numero_componentes": n,
                        "area_total_km2": sum(areas[n]),
                    },
                })
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            entrada = base / "P1_componentes_24194371.geojson"
            entrada.write_text(json.dumps({
                "type": "FeatureCollection", "features": features
            }), encoding="utf-8")
            original = hashlib.sha256(entrada.read_bytes()).hexdigest()
            saida = base / "etapa3"
            with self.assertRaisesRegex(ValueError, "Diagnostico salvo em"):
                executar(entrada, saida)
            self.assertEqual(
                hashlib.sha256(entrada.read_bytes()).hexdigest(), original
            )
            arquivos = list(saida.glob("diagnostico_topologia_*.json"))
            self.assertEqual(len(arquivos), 1)
            d = json.loads(arquivos[0].read_text(encoding="utf-8"))
            self.assertEqual(d["sha256_p1"], original)
            self.assertEqual(d["id_incendio"], 24194371)
            self.assertEqual(d["rank_patch"], 1)
            self.assertTrue(d["area_contada_repetidamente_m2"] > 0)
            self.assertTrue(d["excesso_soma_sobre_patch_m2"] > 0)
            self.assertEqual(d["data_oposta"], "2020-09-11")
            self.assertTrue(d["projecao"]["definicao_laea_proj4"].startswith("+proj=laea"))
            self.assertEqual(list(saida.glob("*_temporais_*.csv")), [])


if __name__ == "__main__":
    unittest.main()
