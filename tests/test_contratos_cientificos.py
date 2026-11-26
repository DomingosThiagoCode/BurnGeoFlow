"""Regressão sintética de conectividade, ancestralidade e representatividade."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pyproj
import shapely
from shapely.geometry import box, mapping, shape

from burngeoflow.processamento.metodologia_v2 import VERSAO, reconstruir


EVENTO = 910
DIA_1 = "2020-01-01"
DIA_2 = "2020-01-03"


class TestContratosCientificos(unittest.TestCase):
    def reconstruir_evento(self, observacoes):
        with TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            origem = raiz / "origem.geojson"
            features = [
                {
                    "type": "Feature",
                    "geometry": mapping(geometria),
                    "properties": {"id_incendio": EVENTO, "data": dia, "rank": rank},
                }
                for dia, geometrias in observacoes.items()
                for rank, geometria in enumerate(geometrias, start=1)
            ]
            origem.write_text(
                json.dumps({"type": "FeatureCollection", "features": features}),
                encoding="utf-8",
            )
            derivados = raiz / "derivados"
            reconstruir(origem, derivados)
            pasta_versao = derivados / VERSAO
            p1 = pasta_versao / f"P1_componentes_{EVENTO}.geojson"
            p2 = pasta_versao / f"P2_regiao_movel_{EVENTO}.geojson"
            features_p1 = json.loads(p1.read_text(encoding="utf-8"))["features"]
            features_p2 = json.loads(p2.read_text(encoding="utf-8"))["features"]
        return features_p1, features_p2

    def test_contato_transitivo_conserva_area_e_mantem_componente_separado(self):
        cadeia = [box(0, 0, 1, 1), box(1, 1, 2, 2), box(2, 2, 3, 3)]
        isolado = box(5, 0, 6, 1)
        p1, _ = self.reconstruir_evento({DIA_1: [*cadeia, isolado]})

        self.assertEqual(len(p1), 2)
        por_ranks = {tuple(f["properties"]["ranks_origem"]): f for f in p1}
        self.assertEqual(por_ranks.keys(), {(1, 2, 3), (4,)})
        grupo = por_ranks[(1, 2, 3)]
        self.assertEqual(shape(grupo["geometry"]).geom_type, "MultiPolygon")

        laea = pyproj.Transformer.from_crs(
            "EPSG:4326",
            "+proj=laea +lon_0=3 +lat_0=1.5 +datum=WGS84 +units=m +no_defs",
            always_xy=True,
        )
        area_cadeia_km2 = sum(
            shapely.transform(patch, laea.transform, interleaved=False).area
            for patch in cadeia
        ) / 1e6
        self.assertAlmostEqual(grupo["properties"]["area_km2"], area_cadeia_km2, places=7)

    def test_contato_temporal_por_borda_ou_vertice_nao_e_ancestral(self):
        anterior = box(0, 0, 1, 1)
        contatos = {"borda": box(1, 0, 2, 1), "vértice": box(1, 1, 2, 2)}
        for contato, final in contatos.items():
            with self.subTest(contato=contato):
                p1, p2 = self.reconstruir_evento({DIA_1: [anterior], DIA_2: [final]})
                self.assertEqual([f["properties"]["data"] for f in p1], [DIA_1, DIA_2])
                self.assertEqual([f["properties"]["data"] for f in p2], [DIA_2])

    def test_ancestral_com_baixa_representatividade_continua_no_p2(self):
        principal = box(0, 0, 1, 1)
        outro_componente = box(10, 0, 18, 8)
        dominante_final = box(0, 0, 9, 9)
        p1, p2 = self.reconstruir_evento({
            DIA_1: [principal, outro_componente],
            DIA_2: [dominante_final, outro_componente],
        })

        self.assertEqual([f["properties"]["data"] for f in p2], [DIA_1, DIA_2])
        ancestral = p2[0]["properties"]
        self.assertEqual(ancestral["rank"], 2)
        total_inicial = sum(
            f["properties"]["area_km2"] for f in p1 if f["properties"]["data"] == DIA_1
        )
        self.assertLess(ancestral["representatividade_pct"], 2.0)
        self.assertAlmostEqual(
            ancestral["representatividade_pct"],
            100 * ancestral["area_km2"] / total_inicial,
        )
