"""Diagnóstico sem mascaramento dos contatos/sobreposições de P1."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch as mock_patch
import unittest

from shapely.geometry import Polygon, box, mapping

from burngeoflow.analises.paisagem import Patch
from burngeoflow.validacao.sobreposicoes import (
    diagnosticar_grupo, diagnosticar_arquivo, verificar_origem, _classificar_origem,
    _intersecao_valida,
)


def patch(rank: int, geometria, *, reparado: bool = False):
    return Patch(
        "2020-09-18", 24340828, rank,
        geometria.area / 1e6, geometria,
        area_m2=geometria.area, perimetro_m=geometria.length,
        reparado_apos_projecao=reparado,
    )


class DiagnosticoGeometrico(unittest.TestCase):

    def test_sobreposicao_original_ou_ausente_preserva_arquivo(self):
        with TemporaryDirectory() as temp:
            p1 = Path(temp) / "P1.geojson"
            geoms = [
                box(-56, -17, -55.98, -16.98),
                box(-55.99, -17, -55.97, -16.98),
                box(-55.90, -17, -55.88, -16.98),
            ]
            feats = []
            for rank, geom in enumerate(geoms, 1):
                feats.append({
                    "type": "Feature", "geometry": mapping(geom),
                    "properties": {
                        "id_incendio": 24340828, "data": "2020-09-18",
                        "rank": rank, "area_km2": float(rank),
                        "numero_componentes": 3, "area_total_km2": 6.0,
                    },
                })
            p1.write_text(json.dumps({
                "type": "FeatureCollection", "features": feats,
            }), encoding="utf-8")
            h = sha256(p1.read_bytes()).hexdigest()
            res = verificar_origem(
                p1, data="2020-09-18", principal=1, outros=(2, 3),
            )
            sobreposto, separado = res["pares"]
            self.assertEqual(
                sobreposto["classificacao"], "JA_EXISTIA_NO_GEOJSON_ORIGINAL"
            )
            self.assertGreater(
                sobreposto["original_wgs84_intersecao_convertida_laea"]["area_m2"],
                0,
            )
            self.assertGreater(
                sobreposto["projetada_laea_apos_reparo"]["area_m2"], 0,
            )
            self.assertEqual(
                separado["classificacao"], "SEM_SOBREPOSICAO_DE_AREA"
            )
            self.assertEqual(
                separado["original_wgs84_intersecao_convertida_laea"]["area_m2"],
                0,
            )
            self.assertEqual(h, sha256(p1.read_bytes()).hexdigest())

    def test_original_invalido_nao_e_atribuido_automaticamente_ao_reparo(self):
        with TemporaryDirectory() as temp:
            p1 = Path(temp) / "P1.geojson"
            cruzado = Polygon([
                (-56, -17), (-55.98, -16.98), (-56, -16.98),
                (-55.98, -17), (-56, -17),
            ])
            outro = box(-55.995, -17.002, -55.985, -16.998)
            feats = []
            for rank, geom in enumerate([cruzado, outro], 1):
                feats.append({
                    "type": "Feature", "geometry": mapping(geom),
                    "properties": {
                        "id_incendio": 24340828, "data": "2020-09-18",
                        "rank": rank, "area_km2": float(rank),
                        "numero_componentes": 2, "area_total_km2": 3.0,
                    },
                })
            p1.write_text(json.dumps({
                "type": "FeatureCollection", "features": feats,
            }), encoding="utf-8")
            res = verificar_origem(
                p1, data="2020-09-18", principal=1, outros=(2,),
            )
            self.assertFalse(res["ranks"]["1"]["original_valida_wgs84"])
            self.assertTrue(res["ranks"]["1"]["reparo_aplicado"])
            self.assertIsNone(
                res["pares"][0]["original_wgs84_intersecao_convertida_laea"]["area_m2"]
            )
            self.assertEqual(
                res["pares"][0]["classificacao"],
                "INDETERMINADO_ORIGINAL_INVALIDO_OU_OVERLAY_IMPOSSIVEL",
            )

    def test_overlay_original_positivo_mantem_prova_quando_projecao_invalida(self):
        # Representa a falha real de 18/09: geometria da intersecao
        # originalmente válida, mas sua reprojeção LAEA ficou inválida.
        a = box(-56, -17, -55.99, -16.99)
        b = box(-55.995, -17, -55.985, -16.99)
        auto_intersectante = Polygon([
            (0, 0), (1, 1), (0, 1), (1, 0), (0, 0),
        ])
        self.assertFalse(auto_intersectante.is_valid)
        tx = SimpleNamespace(transform=lambda x, y: (x, y))
        with mock_patch(
            "burngeoflow.validacao.sobreposicoes.shapely.transform",
            return_value=auto_intersectante,
        ):
            original = _intersecao_valida(a, b, conversor=tx)
        self.assertEqual(original["situacao"], "intersecao_projetada_invalida")
        self.assertIsNone(original["area_m2"])
        self.assertTrue(original["intersecao_original_valida"])
        self.assertTrue(original["sobreposicao_areal_no_original"])
        self.assertGreater(original["area_intersecao_original_graus2"], 0)
        self.assertEqual(
            _classificar_origem(
                original,
                {"area_m2": None},
                {"area_m2": 0.191108208},
            ),
            "JA_EXISTIA_NO_GEOJSON_ORIGINAL",
        )

    def test_intersecao_original_ausente_nao_e_inventada(self):
        a = box(-56, -17, -55.99, -16.99)
        b = box(-55.98, -17, -55.97, -16.99)
        tx = SimpleNamespace(transform=lambda x, y: (x, y))
        original = _intersecao_valida(a, b, conversor=tx)
        self.assertFalse(original["sobreposicao_areal_no_original"])
        self.assertEqual(original["area_intersecao_original_graus2"], 0)
        self.assertEqual(
            _classificar_origem(
                original, {"area_m2": None}, {"area_m2": 0.191108208},
            ),
            "SURGIU_NA_PROJECAO_OU_REPARO_SEM_SEPARACAO_CONFIAVEL",
        )

    def test_projetado_invalido_preserva_incerteza_causal(self):
        s0 = {"area_m2": 0.0}
        s1 = {"area_m2": None}
        s2 = {"area_m2": 0.5}
        self.assertEqual(
            _classificar_origem(s0, s1, s2),
            "SURGIU_NA_PROJECAO_OU_REPARO_SEM_SEPARACAO_CONFIAVEL",
        )

    def test_ranks_exigidos_precisam_existir(self):
        with TemporaryDirectory() as temp:
            p1 = Path(temp) / "P1.geojson"
            g = box(-56, -17, -55.99, -16.99)
            p1.write_text(json.dumps({
                "type": "FeatureCollection", "features": [{
                    "type": "Feature", "geometry": mapping(g),
                    "properties": {
                        "id_incendio": 24340828, "data": "2020-09-18",
                        "rank": 1, "area_km2": 1.0,
                        "numero_componentes": 1, "area_total_km2": 1.0,
                    },
                }],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ranks inexistentes"):
                verificar_origem(p1, data="2020-09-18", outros=(18,))

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
