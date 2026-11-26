"""Ensaios sintéticos de partição, sem tolerância ou reparo científico."""
import unittest

from shapely.geometry import Polygon, box

from burngeoflow.validacao.particao_faces_experimental import auditar_faces


class TestParticaoFacesExperimental(unittest.TestCase):
    def test_sucessores_sobrepostos_geram_face_ambigua(self):
        a, b = box(0, 0, 4, 4), box(2, 0, 6, 4)
        resumo = auditar_faces([(3, a), (83, b)])
        self.assertAlmostEqual(resumo["area_uniao_m2"], 24)
        self.assertAlmostEqual(resumo["area_soma_componentes_m2"], 32)
        self.assertAlmostEqual(resumo["area_faces_compartilhadas_m2"], 8)
        self.assertAlmostEqual(resumo["area_contada_repetidamente_m2"], 8)
        self.assertEqual(resumo["quantidade_faces"], 3)
        self.assertAlmostEqual(resumo["residuo_particao_m2"], 0)
        self.assertAlmostEqual(resumo["residuo_multiplicidade_m2"], 0)
        compartilhada = next(
            f for f in resumo["faces_por_conjunto_de_ranks"]
            if f["ranks_cobertura"] == [3, 83]
        )
        self.assertAlmostEqual(compartilhada["area_m2"], 8)
        self.assertIn("INDEFINIDA", resumo["politica_atribuicao"])

    def test_tripla_cobertura_conta_multiplicidade_sem_atribuicao(self):
        geom = box(0, 0, 2, 2)
        resumo = auditar_faces([(1, geom), (2, geom), (3, geom)])
        self.assertAlmostEqual(resumo["area_uniao_m2"], 4)
        self.assertAlmostEqual(resumo["area_faces_compartilhadas_m2"], 4)
        self.assertAlmostEqual(resumo["area_contada_repetidamente_m2"], 8)
        self.assertEqual(resumo["quantidade_faces"], 1)

    def test_contato_so_por_vertice_nao_cria_dupla_area(self):
        resumo = auditar_faces([
            (1, box(0, 0, 2, 2)),
            (2, box(2, 2, 4, 4)),
        ])
        self.assertAlmostEqual(resumo["area_uniao_m2"], 8)
        self.assertEqual(resumo["area_faces_compartilhadas_m2"], 0)
        self.assertEqual(resumo["quantidade_faces"], 2)

    def test_contato_por_aresta_nao_cria_face_compartilhada(self):
        resumo = auditar_faces([
            (1, box(0, 0, 2, 2)),
            (2, box(2, 0, 4, 2)),
        ])
        self.assertEqual(resumo["area_faces_compartilhadas_m2"], 0)
        self.assertAlmostEqual(resumo["area_uniao_m2"], 8)

    def test_buraco_nao_e_confundido_com_area_queimada(self):
        vazado = Polygon(
            [(0, 0), (10, 0), (10, 10), (0, 10)],
            holes=[[(3, 3), (7, 3), (7, 7), (3, 7)]],
        )
        interior = box(4, 4, 6, 6)
        resumo = auditar_faces([(1, vazado), (2, interior)])
        self.assertAlmostEqual(resumo["area_uniao_m2"], 88)
        self.assertAlmostEqual(resumo["area_soma_componentes_m2"], 88)
        self.assertEqual(resumo["area_faces_compartilhadas_m2"], 0)

    def test_geometrias_originais_sao_preservadas(self):
        a, b = box(0, 0, 4, 4), box(2, 0, 6, 4)
        bruto_a, bruto_b = a.wkb, b.wkb
        resumo = auditar_faces([(1, a), (2, b)], com_geometrias=True)
        self.assertEqual(a.wkb, bruto_a)
        self.assertEqual(b.wkb, bruto_b)
        self.assertEqual(resumo["faces"][0]["geometria"]["type"], "Polygon")

    def test_rejeita_autointersecao_antes_de_pretender_particionar(self):
        invalida = Polygon([(0, 0), (3, 3), (0, 3), (3, 0)])
        self.assertFalse(invalida.is_valid)
        with self.assertRaisesRegex(ValueError, "geometria poligonal"):
            auditar_faces([(1, invalida)])

    def test_rejeita_ranks_duplicados_e_entrada_vazia(self):
        with self.assertRaisesRegex(ValueError, "Ranks"):
            auditar_faces([
                (1, box(0, 0, 1, 1)),
                (1, box(2, 2, 3, 3)),
            ])
        with self.assertRaisesRegex(ValueError, "ao menos"):
            auditar_faces([])


if __name__ == "__main__":
    unittest.main()
