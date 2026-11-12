"""Diagnóstico sem mascaramento dos contatos/sobreposições de P1."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shapely.geometry import box, mapping

from burngeoflow.analises.paisagem import Patch
from burngeoflow.validacao.sobreposicoes import (
    diagnosticar_grupo, diagnosticar_arquivo,
)


def patch(rank: int, geometria, *, reparado: bool = False):
    return Patch(
        "2020-09-18", 24340828, rank,
        geometria.area / 1e6, geometria,
        area_m2=geometria.area, perimetro_m=geometria.length,
        reparado_apos_projecao=reparado,
    )


class DiagnosticoGeometrico(unittest.TestCase):
    def test_intersecao_identifica_ranks_area_e_reparos(self):
        patches = [
            patch(1, box(0, 0, 10, 10)),
            patch(2, box(5, 0, 15, 10), reparado=True),
        ]
        r = diagnosticar_grupo(patches)
        self.assertEqual(r["numero_pares_sobrepostos"], 1)
        self.assertAlmostEqual(r["excesso_area_somada_sobre_uniao_m2"], 50)
        self.assertAlmostEqual(r["maior_intersecao_par_m2"], 50)
        self.assertEqual(
            (r["pares_mais_relevantes"][0]["rank_a"],
             r["pares_mais_relevantes"][0]["rank_b"]), (1, 2),
        )
        self.assertTrue(r["pares_mais_relevantes"][0]
                        ["b_reparado_apos_projecao"])

    def test_contato_pontual_e_borda_nao_sao_sobreposicao(self):
        a = patch(1, box(0, 0, 10, 10))
        b = patch(2, box(10, 0, 20, 10))
        c = patch(3, box(20, 10, 30, 20))
        r = diagnosticar_grupo([a, b, c])
        self.assertEqual(r["numero_pares_sobrepostos"], 0)
        self.assertAlmostEqual(r["excesso_area_somada_sobre_uniao_m2"], 0)

    def test_intersecao_tripla_nao_e_confundida_com_excesso_total(self):
        patches = [
            patch(1, box(0, 0, 10, 10)),
            patch(2, box(0, 0, 10, 10)),
            patch(3, box(0, 0, 10, 10)),
        ]
        r = diagnosticar_grupo(patches)
        self.assertEqual(r["numero_pares_sobrepostos"], 3)
        self.assertAlmostEqual(r["excesso_area_somada_sobre_uniao_m2"], 200)
        self.assertAlmostEqual(r["soma_intersecoes_pares_m2"], 300)

    def test_diagnostico_arquivo_nao_modifica_p1(self):
        with TemporaryDirectory() as temp:
            p1 = Path(temp) / "P1.geojson"
            a = box(-56, -17, -55.99, -16.99)
            b = box(-55.995, -17, -55.985, -16.99)
            features = []
            for rank, geom in enumerate((a, b), 1):
                features.append({
                    "type": "Feature", "geometry": mapping(geom),
                    "properties": {
                        "id_incendio": 24340828,
                        "data": "2020-09-18",
                        "rank": rank,
                        "area_km2": 1.0,
                        "numero_componentes": 2,
                        "area_total_km2": 2.0,
                    },
                })
            p1.write_text(json.dumps({
                "type": "FeatureCollection", "features": features,
            }), encoding="utf-8")
            antes = sha256(p1.read_bytes()).hexdigest()
            r = diagnosticar_arquivo(p1, data="2020-09-18")
            self.assertEqual(r["datas_avaliadas"], 1)
            self.assertEqual(r["datas_que_excedem_1m2"], ["2020-09-18"])
            self.assertGreater(r["datas"][0]["maior_intersecao_par_m2"], 1)
            self.assertEqual(antes, sha256(p1.read_bytes()).hexdigest())
            self.assertEqual(r["datas"][0]["pares_mais_relevantes"][0]
                             ["p1_a_original"]["validade_wgs84"], True)

    def test_data_inexistente_rejeitada(self):
        with TemporaryDirectory() as temp:
            p1 = Path(temp) / "P1.geojson"
            a = box(-56, -17, -55.99, -16.99)
            p1.write_text(json.dumps({
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature", "geometry": mapping(a),
                    "properties": {
                        "id_incendio": 24340828,
                        "data": "2020-09-18",
                        "rank": 1,
                        "area_km2": 1,
                        "numero_componentes": 1,
                        "area_total_km2": 1,
                    }
                }],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Data inexistente"):
                diagnosticar_arquivo(p1, data="2020-09-19")


if __name__ == "__main__":
    unittest.main()
