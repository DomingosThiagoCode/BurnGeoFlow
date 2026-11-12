"""Regressão da consolidação TR/IGT com P2 inválido após projeção LAEA."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import shapely
from shapely.geometry import Polygon, box, mapping

from burngeoflow.analises.tr_igt import (
    executar, geometrias_p2_consolidadas,
)
from burngeoflow.analises.paisagem import carregar_p1, projetar_patches


ID = 24340828
DATAS = ("2020-08-09", "2020-08-10")
BOWTIE = Polygon([
    (-56.0, -17.0), (-55.999, -16.999), (-56.0, -16.999),
    (-55.999, -17.0), (-56.0, -17.0),
])


def criar_geojsons(pasta: Path, *, divergente: bool = False):
    """P1 = make_valid do mesmo desenho GEE; P2 mantém anel cruzado."""
    geom_p1 = shapely.make_valid(BOWTIE)
    geom_p2 = box(-55.9, -16.9, -55.8, -16.8) if divergente else BOWTIE
    p1, p2 = [], []
    for pos, data in enumerate(DATAS, start=1):
        props = {
            "id_incendio": ID, "ano_dataset": 2020, "data": data,
            "rank": 1, "area_km2": 0.006,
            "numero_componentes": 1, "area_total_km2": 0.006,
        }
        p1.append({"type": "Feature", "geometry": mapping(geom_p1),
                   "properties": dict(props)})
        p2prop = dict(props)
        p2prop.update({
            "rank_global": 1, "ordem_temporal": pos,
            "delta_area_km2": 0.0, "delta_area_total_km2": 0.0,
            "metodo_continuidade": "inicial_maior_area" if pos == 1
                                  else "sobreposicao",
        })
        p2.append({"type": "Feature", "geometry": mapping(geom_p2),
                   "properties": p2prop})
    arquivo_p1, arquivo_p2 = pasta/"P1.geojson", pasta/"P2.geojson"
    arquivo_p1.write_text(json.dumps({"type": "FeatureCollection",
                                     "features": p1}), encoding="utf-8")
    arquivo_p2.write_text(json.dumps({"type": "FeatureCollection",
                                     "features": p2}), encoding="utf-8")
    return arquivo_p1, arquivo_p2


class TesteConsolidacaoTopologica(unittest.TestCase):
    def test_consolidacao_utiliza_p1_canonico_ao_reparar_p2(self):
        with TemporaryDirectory() as d:
            pasta = Path(d)
            arq_p1, arq_p2 = criar_geojsons(pasta)
            patches = carregar_p1(arq_p1)
            projecao, _ = projetar_patches(patches)
            geoms, auditoria = geometrias_p2_consolidadas(
                arq_p1, arq_p2, id_incendio=ID,
                definicao_laea=projecao["definicao_laea_proj4"],
            )
            self.assertEqual(set(geoms), set(DATAS))
            self.assertTrue(all(g.is_valid and g.area > 0 for g in geoms.values()))
            self.assertEqual(auditoria["numero_reparos_p2_para_comparacao"], 2)
            self.assertLess(auditoria["maior_diferenca_simetrica_p1_p2_m2"], 1.0)
            self.assertAlmostEqual(geoms[DATAS[0]].area, patches[0].geometria.area)

    def test_tr_igt_completo_reutiliza_topologia_p1(self):
        with TemporaryDirectory() as d:
            pasta = Path(d)
            arq_p1, arq_p2 = criar_geojsons(pasta)
            saida = pasta/"saida"
            resumo = executar(arq_p1, arq_p2, saida)
            self.assertEqual((resumo["datas"], resumo["transicoes"]), (2, 1))
            self.assertEqual(resumo["correspondencia_p1_p2"], "2/2")
            self.assertEqual(
                resumo["auditoria_geometrica_consolidacao"]
                      ["numero_reparos_p2_para_comparacao"], 2,
            )
            self.assertTrue((saida/f"comparacao_tr_igt_{ID}.csv").exists())
            self.assertTrue((saida/f"componentes_reducao_{ID}.csv").exists())

    def test_rejeita_p2_espacialmente_divergente(self):
        with TemporaryDirectory() as d:
            pasta = Path(d)
            arq_p1, arq_p2 = criar_geojsons(pasta, divergente=True)
            patches = carregar_p1(arq_p1)
            projecao, _ = projetar_patches(patches)
            with self.assertRaisesRegex(ValueError, "geometria diverge do P1"):
                geometrias_p2_consolidadas(
                    arq_p1, arq_p2, id_incendio=ID,
                    definicao_laea=projecao["definicao_laea_proj4"],
                )


if __name__ == "__main__":
    unittest.main()