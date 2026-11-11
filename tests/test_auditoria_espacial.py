"""Casos sinteticos para evitar depender apenas do incendio de referencia."""

import unittest
from pathlib import Path

import shapely
from shapely.geometry import Polygon

from burngeoflow.validacao.espacial import (
    Feicao,
    agrupar,
    evolucao_temporal,
    ler,
    preparar_metrico,
    relacao_p2_p1,
    resumo_geometrias,
    sobreposicoes_p1,
)


def feicao(geom, data, rank, indice=0):
    valida = geom.is_valid
    return Feicao(
        indice=indice,
        data=data,
        rank=rank,
        propriedades={"data": data, "rank": rank, "area_km2": 1.0},
        geometria=geom,
        valida=valida,
        motivo_invalidez=None if valida else shapely.is_valid_reason(geom),
        geometria_diagnostica=geom,
    )


def quadrado(x1, y1, x2, y2):
    return Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])


class TesteAuditoriaEspacial(unittest.TestCase):
    def test_poligono_autointersectado_e_detectado(self):
        bowtie = Polygon([(-57, -16), (-56.99, -15.99),
                          (-57, -15.99), (-56.99, -16)])
        f = feicao(bowtie, "2020-01-01", 1)
        preparar_metrico([f], [])
        d = resumo_geometrias([f])
        self.assertEqual(d["invalidas_planas_em_lonlat"], 1)
        self.assertEqual(d["invalidas_apos_projecao_laea"], 1)
        self.assertEqual(d["reparos_geraram_multipolygon"], 1)
        self.assertGreaterEqual(d["max_partes_no_reparo"], 2)

    def test_reprojecao_vem_antes_de_regularizar(self):
        raiz = Path(__file__).resolve().parents[1]
        p1_path = raiz / "dados/estudo_caso_24340828/P1_componentes_24340828.geojson"
        p1 = ler(p1_path)
        invalidos_lonlat = [f for f in p1 if not f.valida]
        self.assertEqual(len(invalidos_lonlat), 172)
        for f in invalidos_lonlat:
            self.assertIs(f.geometria_diagnostica, f.geometria)
        preparar_metrico(p1, [])
        r = resumo_geometrias(p1)
        self.assertEqual(r["invalidas_planas_em_lonlat"], 172)
        self.assertEqual(r["invalidas_apos_projecao_laea"], 0)
        self.assertEqual(r["reparos_condicionais_apos_projecao"], 0)
        self.assertEqual(r["reparos_geraram_multipolygon"], 0)
        self.assertTrue(all(f.metrico.is_valid for f in p1))

    def test_detecta_sobreposicao_de_areas_entre_patches(self):
        p1 = [feicao(quadrado(-57, -16, -56.998, -15.998), "2020-01-01", 1),
              feicao(quadrado(-56.999, -15.999, -56.997, -15.997), "2020-01-01", 2)]
        preparar_metrico(p1, [])
        r = sobreposicoes_p1(agrupar(p1))
        self.assertEqual(r["pares_com_sobreposicao_de_area"], 1)

    def test_p2_igual_ao_p1_mesmo_com_ordem_de_vertices_diferente(self):
        g = quadrado(-57, -16, -56.999, -15.999)
        p1 = [feicao(g, "2020-01-01", 1)]
        p2 = [feicao(Polygon(list(reversed(g.exterior.coords))), "2020-01-01", 1)]
        preparar_metrico(p1, p2)
        r = relacao_p2_p1(agrupar(p1), p2)
        self.assertEqual(r["equivalentes_topologicamente_apos_projecao"], 1)
        self.assertEqual(r["coincidencia_estrita_coordenadas"], 0)

    def test_caso_sintetico_de_fusao_e_crescimento_acumulado(self):
        antiga1 = feicao(quadrado(-57.010, -16, -57.008, -15.998), "2020-01-01", 1)
        antiga2 = feicao(quadrado(-57.006, -16, -57.004, -15.998), "2020-01-01", 2)
        nova = feicao(quadrado(-57.011, -16.001, -57.003, -15.997), "2020-01-02", 1)
        p1 = [antiga1, antiga2, nova]
        p2 = [antiga1, nova]
        preparar_metrico(p1, p2)
        r = evolucao_temporal(agrupar(p1), p2)
        self.assertEqual(r["fusoes_candidatas_por_sobreposicao"], 1)
        self.assertEqual(r["intervalos_residuo_evento_acima_100m2"], 0)
        self.assertEqual(r["intervalos_residuo_rm_acima_100m2"], 0)


if __name__ == "__main__":
    unittest.main()
