"""Regressao de comportamentos que nao devem ser presumidos para outros IDs."""

import unittest

import shapely
from shapely.geometry import Polygon

from scripts.comparar_regularizacao import partes_poligonais


class TesteComparacaoRegularizacao(unittest.TestCase):
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
