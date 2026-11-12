"""Regressões: sobreposição P1, balanço de áreas e pendências da Etapa 6."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shapely.geometry import box, mapping

from burngeoflow.analises.integracao import (
    calcular_cobertura_componentes, conferir_balanco_componentes,
    ler_geometrias,
)
from burngeoflow.validacao.robustez import evidencias


class TesteAreaCoberta(unittest.TestCase):
    def test_soma_nao_e_area_da_uniao_quando_patches_sobrepoem(self):
        a = box(0, 0, 10, 10)
        b = box(5, 0, 15, 10)
        totais, auditoria = calcular_cobertura_componentes(
            {"2020-09-18": [a, b]}, {"2020-09-18": [3, 4]},
        )
        registro = auditoria["datas"][0]
        self.assertEqual(registro["soma_patches_m2"], 200)
        self.assertEqual(registro["cobertura_uniao_m2"], 150)
        self.assertEqual(registro["excesso_sobreposicao_m2"], 50)
        self.assertEqual(totais["2020-09-18"].area, 150)
        self.assertEqual(
            registro["pares_exemplos"][0]["rank_p1_a"], 3,
        )
        self.assertEqual(
            registro["pares_exemplos"][0]["rank_p1_b"], 4,
        )
        self.assertEqual(
            auditoria["datas_com_sobreposicao_acima_1m2"], ["2020-09-18"],
        )

    def test_sem_sobreposicao_nao_inventa_alerta(self):
        totais, auditoria = calcular_cobertura_componentes(
            {"2020-09-18": [box(0, 0, 10, 10), box(20, 0, 30, 10)]}
        )
        self.assertEqual(totais["2020-09-18"].area, 200)
        self.assertEqual(auditoria["datas_com_sobreposicao_acima_1m2"], [])

    def test_balanco_conserva_variacao_da_soma_p1(self):
        # Cobertura cresceu 50 m², sobreposição caiu 25 m².
        # Portanto a SOMA de patches aumentou somente 25 m².
        cobertura = conferir_balanco_componentes(
            200 / 1e6, 150 / 1e6,
            25 / 1e6, 50 / 1e6,
            25 / 1e6, "transicao 17->18 setembro",
        )
        self.assertAlmostEqual(cobertura, 50/1e6)
        with self.assertRaisesRegex(ValueError, "Inconsistencia"):
            conferir_balanco_componentes(
                200/1e6, 150/1e6, 25/1e6, 50/1e6,
                75/1e6, "transicao irregular",
            )

    def test_integracao_reconciliada_aceita_p1_com_overlap_reportado(self):
        with TemporaryDirectory() as temp:
            pasta = Path(temp)
            # Dois patches geometricamente válidos mas não disjuntos.
            primeiro = box(-56.0, -17.0, -55.99, -16.99)
            segundo = box(-55.995, -17.0, -55.985, -16.99)
            p1_features, p2_features = [], []
            for numero, dia in enumerate(("2020-09-17", "2020-09-18"), 1):
                for rank, geom in enumerate((primeiro, segundo), 1):
                    props = {
                        "id_incendio": 24340828,
                        "data": dia, "rank": rank,
                        "area_km2": 1.0,
                        "numero_componentes": 2,
                        "area_total_km2": 2.0,
                    }
                    p1_features.append({
                        "type": "Feature", "geometry": mapping(geom),
                        "properties": props,
                    })
                p2_features.append({
                    "type": "Feature",
                    "geometry": mapping(primeiro),
                    "properties": {
                        "id_incendio": 24340828, "data": dia,
                        "rank_global": 1,
                    },
                })
            p1 = pasta / "P1.geojson"
            p2 = pasta / "P2.geojson"
            p1.write_text(json.dumps({
                "type": "FeatureCollection", "features": p1_features,
            }), encoding="utf-8")
            p2.write_text(json.dumps({
                "type": "FeatureCollection", "features": p2_features,
            }), encoding="utf-8")
            originais = (p1.read_bytes(), p2.read_bytes())
            diagnostico = {}
            total, selecionados, grupos, _ = ler_geometrias(
                p1, p2, 24340828, diagnostico=diagnostico,
            )
            self.assertEqual(len(total), 2)
            self.assertEqual(len(selecionados), 2)
            self.assertEqual(len(grupos["2020-09-18"]), 2)
            self.assertLess(
                total["2020-09-18"].area,
                sum(p.area for p in grupos["2020-09-18"]),
            )
            self.assertIn(
                "2020-09-18",
                diagnostico["cobertura_p1"]["datas_com_sobreposicao_acima_1m2"],
            )
            self.assertEqual((p1.read_bytes(), p2.read_bytes()), originais)


class TesteEvidenciaDinamica(unittest.TestCase):
    def test_numero_de_convergencias_e_fases_nao_e_fixado_no_codigo(self):
        dados = evidencias(8, 2)
        afirmacoes = [item["afirmacao"] for item in dados]
        self.assertTrue(any(x.startswith("8 convergencias") for x in afirmacoes))
        self.assertTrue(any(x.startswith("2 fases") for x in afirmacoes))
        self.assertFalse(any(x.startswith("72 convergencias") for x in afirmacoes))


if __name__ == "__main__":
    unittest.main()
