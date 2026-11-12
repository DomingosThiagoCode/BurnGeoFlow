"""Testes da reconciliação topológica sem chamadas ao Earth Engine."""
from __future__ import annotations

from types import SimpleNamespace
import unittest

import shapely
from shapely.geometry import Polygon, box, GeometryCollection, LineString

from burngeoflow.validacao.topologia_p2 import (
    ErroConciliacao, _areal, reconciliar_p2,
)


class Identidade:
    @staticmethod
    def transform(x, y):
        return x, y


class TesteReconciliacao(unittest.TestCase):
    def test_poligono_valido_sem_reparo(self):
        original = box(0, 0, 10, 10)
        patch = SimpleNamespace(geometria=original)
        resultado, auditoria = reconciliar_p2(
            original, patch, Identidade(), registro=6,
            data="2020-08-16", rank=1,
        )
        self.assertTrue(resultado.is_valid)
        self.assertFalse(auditoria["reparo_p2_necessario"])
        self.assertAlmostEqual(auditoria["diferenca_simetrica_m2"], 0)

    def test_autoriza_make_valid_so_para_p2_equivalente_ao_p1(self):
        invalido = Polygon([(0, 0), (4, 4), (0, 4), (4, 0), (0, 0)])
        self.assertFalse(invalido.is_valid)
        referencia = shapely.make_valid(invalido)
        patch = SimpleNamespace(geometria=referencia)
        resultado, auditoria = reconciliar_p2(
            invalido, patch, Identidade(), registro=6,
            data="2020-08-16", rank=1,
        )
        self.assertTrue(resultado.is_valid)
        self.assertTrue(auditoria["reparo_p2_necessario"])
        self.assertIn("Self-intersection", auditoria["motivo_original"])
        self.assertAlmostEqual(auditoria["diferenca_simetrica_m2"], 0)

    def test_rejeita_poligono_nao_equivalente_apesar_de_reparo(self):
        invalido = Polygon([(0, 0), (8, 8), (0, 8), (8, 0), (0, 0)])
        referencia = shapely.make_valid(
            Polygon([(0, 0), (4, 4), (0, 4), (4, 0), (0, 0)])
        )
        patch = SimpleNamespace(geometria=referencia)
        with self.assertRaisesRegex(ErroConciliacao, "diverge do P1"):
            reconciliar_p2(invalido, patch, Identidade(),
                           registro=6, data="2020-08-16", rank=1)

    def test_erro_inclui_registro_data_e_rank(self):
        patch = SimpleNamespace(geometria=box(0, 0, 10, 10))
        with self.assertRaisesRegex(ErroConciliacao,
                                    r"registro 6 \(2020-08-16, rank 2\)"):
            reconciliar_p2(box(20, 20, 30, 30), patch,
                           Identidade(), registro=6,
                           data="2020-08-16", rank=2)

    def test_geometrycollection_nao_gera_areas_artificiais(self):
        colecao = GeometryCollection([
            box(0, 0, 10, 10), LineString([(0, 0), (1, 1)])
        ])
        poligono = _areal(colecao)
        self.assertTrue(poligono.is_valid)
        self.assertAlmostEqual(poligono.area, 100)

    def test_nao_aceita_geometria_sem_area(self):
        patch = SimpleNamespace(geometria=box(0, 0, 10, 10))
        with self.assertRaisesRegex(ErroConciliacao, "polígono válido"):
            reconciliar_p2(LineString([(0, 0), (10, 10)]), patch,
                           Identidade(), registro=6,
                           data="2020-08-16", rank=1)


if __name__ == "__main__":
    unittest.main()