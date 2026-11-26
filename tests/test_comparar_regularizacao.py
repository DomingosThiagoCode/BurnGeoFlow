"""Regressao de comportamentos que nao devem ser presumidos para outros IDs."""

import unittest

import shapely
from shapely.geometry import Polygon

from burngeoflow.validacao.regularizacao import partes_poligonais, comparar
from tempfile import TemporaryDirectory
from pathlib import Path
import json
from unittest.mock import patch
from burngeoflow.validacao import regularizacao


class TesteComparacaoRegularizacao(unittest.TestCase):
    def test_p1_processado_uma_vez(self):
        feat = {"type":"Feature","properties":{"data":"2020-01-01","rank":1,"area_km2":1},
                "geometry":{"type":"Polygon","coordinates":[[[0,0],[.01,0],[.01,.01],[0,.01],[0,0]]]}}
        with TemporaryDirectory() as d:
            a,b = Path(d)/"p1.json",Path(d)/"p2.json"
            for p in (a,b):
                p.write_text(json.dumps({"type":"FeatureCollection","features":[feat]}))
            with patch.object(regularizacao,"processar",wraps=regularizacao.processar) as proc:
                r=comparar(a,b)
                self.assertEqual(proc.call_count,2)
                self.assertEqual(r["p1"]["total"],1)
                self.assertEqual(r["p2"]["total"],1)
                self.assertEqual(r["p1"]["comparacao"],r["p2"]["comparacao"])

    def test_bowtie_make_valid_preserva_duas_partes(self):
        bowtie = Polygon([(0, 0), (2, 2), (0, 2), (2, 0)])
        mv = shapely.make_valid(bowtie)
        b0 = bowtie.buffer(0)
        self.assertFalse(bowtie.is_valid)
        self.assertTrue(mv.is_valid)
        self.assertTrue(b0.is_valid)
        self.assertEqual(partes_poligonais(mv), 2)
        self.assertEqual(partes_poligonais(b0), 1)
        self.assertAlmostEqual(mv.area, 2.0)
        self.assertAlmostEqual(b0.area, 1.0)


if __name__ == "__main__":
    unittest.main()
