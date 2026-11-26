"""Casos controlados do balanço geométrico D-005 em coordenadas LAEA."""
import unittest

from shapely.geometry import LineString, box

from burngeoflow.analises.incrementos import calcular_balanco_expansao_p2


class TesteBalancoExpansaoP2(unittest.TestCase):
    def test_fusao_com_area_nova_perda_e_sobreposicao_em_p1(self):
        anterior = box(0, 0, 4, 4)
        atual = box(1, 0, 9, 4)
        p1 = [
            anterior,
            box(5, 0, 7, 4),
            box(6, 0, 8, 4),
            box(10, 0, 11, 4),
        ]
        self.assertEqual(calcular_balanco_expansao_p2(anterior, atual, p1), {
            "expansao_bruta_m2": 20.0,
            "area_nova_observada_m2": 8.0,
            "area_previamente_queimada_incorporada_m2": 12.0,
            "area_perdida_m2": 4.0,
            "variacao_liquida_m2": 16.0,
            "p2_anterior_fora_p1_m2": 0.0,
            "erro_particao_expansao_m2": 0.0,
        })

    def test_estabilidade_e_contato_sem_area_incorporada(self):
        anterior = box(0, 0, 2, 2)
        p1 = [anterior, box(3, 0, 4, 2)]
        estavel = calcular_balanco_expansao_p2(anterior, anterior, p1)
        self.assertTrue(all(valor == 0 for valor in estavel.values()))
        ampliado = calcular_balanco_expansao_p2(anterior, box(0, 0, 3, 2), p1)
        self.assertEqual(ampliado["expansao_bruta_m2"], 2)
        self.assertEqual(ampliado["area_nova_observada_m2"], 2)
        self.assertEqual(ampliado["area_previamente_queimada_incorporada_m2"], 0)

    def test_p2_anterior_fora_de_p1_e_exposto_sem_correcao(self):
        anterior = box(0, 0, 4, 4)
        balanco = calcular_balanco_expansao_p2(anterior, anterior, [box(0, 0, 3, 4)])
        self.assertEqual(balanco["p2_anterior_fora_p1_m2"], 4)
        self.assertEqual(balanco["erro_particao_expansao_m2"], 4)

    def test_rejeita_p1_ausente_e_geometria_sem_area(self):
        p2 = box(0, 0, 2, 2)
        with self.assertRaisesRegex(ValueError, "P1 anterior"):
            calcular_balanco_expansao_p2(p2, p2, [])
        with self.assertRaisesRegex(ValueError, "polígonos válidos"):
            calcular_balanco_expansao_p2(p2, p2, [LineString([(0, 0), (1, 0)])])


if __name__ == "__main__":
    unittest.main()
