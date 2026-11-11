"""Testes analiticos, de topologia e de regressao da Etapa 2."""

from __future__ import annotations

import json
import hashlib
from math import isclose, pi, sqrt
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from shapely.geometry import Point, box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from calcular_metricas_paisagem import (  # noqa: E402
    Patch, calcular_metricas, carregar_p1, examinar_contatos,
    executar, indice_forma_vetorial, projetar_patches,
    sensibilidade_contato_vetorial,
)


def patch_sintetico(data: str, rank: int, geom: object) -> Patch:
    p = Patch(data, 123, rank, geom.area / 1e6, geom)
    p.area_m2, p.perimetro_m = geom.area, geom.length
    return p


class MetricasAnaliticasTests(unittest.TestCase):
    def test_indice_forma_quadrado_e_circulo(self):
        quadrado = box(0, 0, 1000, 1000)
        esperado = 2 / sqrt(pi)
        self.assertAlmostEqual(
            indice_forma_vetorial(quadrado.area, quadrado.length), esperado
        )
        circulo = Point(0, 0).buffer(1000, quad_segs=128)
        self.assertAlmostEqual(
            indice_forma_vetorial(circulo.area, circulo.length), 1,
            places=4
        )
        with self.assertRaises(ValueError):
            indice_forma_vetorial(0, 10)

    def test_evolucao_dominancia_taxa_e_distancias(self):
        d1 = [
            patch_sintetico("2020-01-01", 1, box(0, 0, 2000, 2000)),
            patch_sintetico("2020-01-01", 2, box(5000, 0, 6000, 1000)),
        ]
        d2 = [
            patch_sintetico("2020-01-03", 1, box(0, 0, 3000, 2000)),
            patch_sintetico("2020-01-03", 2, box(5000, 0, 6000, 1000)),
        ]
        p, t, s, resumo = calcular_metricas(d1 + d2)
        self.assertEqual(len(p), 4)
        self.assertEqual(len(t), 2)
        self.assertAlmostEqual(p[0]["distancia_vizinho_mais_proximo_km"], 3)
        self.assertAlmostEqual(p[0]["participacao_area_queimada_pct"], 80)
        self.assertEqual(t[0]["numero_patches"], 2)
        self.assertAlmostEqual(t[0]["area_total_laea_km2"], 5)
        self.assertAlmostEqual(t[0]["dominancia_maior_patch_pct"], 80)
        self.assertIsNone(t[0]["area_nova_intervalo_laea_km2"])
        self.assertIsNone(t[0]["taxa_media_intervalo_km2_dia"])
        self.assertEqual(t[1]["dias_desde_observacao_anterior"], 2)
        self.assertAlmostEqual(t[1]["area_nova_intervalo_laea_km2"], 2)
        self.assertAlmostEqual(t[1]["taxa_media_intervalo_km2_dia"], 1)
        self.assertEqual(s[0]["numero_grupos_por_contato_vetorial"], 2)
        self.assertEqual(resumo["lacunas_maiores_1_dia"],
                         [{"data": "2020-01-03", "dias": 2}])

    def test_contatos_em_ponto_e_borda_sao_diferentes(self):
        p1 = patch_sintetico("2020-01-01", 1, box(0, 0, 1, 1))
        p2 = patch_sintetico("2020-01-01", 2, box(1, 1, 2, 2))
        p3 = patch_sintetico("2020-01-01", 3, box(2, 1, 3, 2))
        resultado = examinar_contatos([p1, p2, p3])
        self.assertEqual(resultado["contatos_pontuais"], 1)
        self.assertEqual(resultado["contatos_por_borda"], 1)
        self.assertEqual(resultado["sobreposicoes_maiores_1m2"], 0)
        agrupado = sensibilidade_contato_vetorial([p1, p2, p3])
        self.assertEqual(agrupado["numero_grupos_por_contato_vetorial"], 1)
        self.assertEqual(len([p1, p2, p3]), 3)  # P1 original preservado

    def test_um_patch_nao_tem_vizinho(self):
        unico = patch_sintetico("2020-01-01", 1, box(0, 0, 1000, 1000))
        p, t, s, _ = calcular_metricas([unico])
        self.assertIsNone(p[0]["distancia_vizinho_mais_proximo_km"])
        self.assertEqual(t[0]["dominancia_maior_patch_pct"], 100)
        self.assertEqual(s[0]["numero_grupos_por_contato_vetorial"], 1)

    def test_sobreposicao_real_e_registrada(self):
        a = patch_sintetico("2020-01-01", 1, box(0, 0, 3, 3))
        b = patch_sintetico("2020-01-01", 2, box(1, 1, 4, 4))
        self.assertEqual(
            examinar_contatos([a, b])["sobreposicoes_maiores_1m2"], 1
        )

    def test_acumulado_decrescente_rejeitado(self):
        d1 = patch_sintetico("2020-01-01", 1, box(0, 0, 2000, 2000))
        d2 = patch_sintetico("2020-01-02", 1, box(0, 0, 1000, 1000))
        with self.assertRaisesRegex(ValueError, "area acumulada diminuiu"):
            calcular_metricas([d1, d2])


class EntradaTests(unittest.TestCase):
    @staticmethod
    def feicao(geom, data, rank, n, total, incendio=123):
        return {
            "type": "Feature", "geometry": mapping(geom),
            "properties": {"data": data, "id_incendio": incendio,
                           "rank": rank, "numero_componentes": n,
                           "area_km2": total / n, "area_total_km2": total},
        }

    def test_ranks_duplicados_rejeitados(self):
        geom = box(-57, -16, -56.99, -15.99)
        colecao = {"type": "FeatureCollection", "features": [
            self.feicao(geom, "2020-01-01", 1, 2, 2),
            self.feicao(geom, "2020-01-01", 1, 2, 2),
        ]}
        with TemporaryDirectory() as diretorio:
            arquivo = Path(diretorio) / "p1.geojson"
            arquivo.write_text(json.dumps(colecao), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ranks"):
                carregar_p1(arquivo)

    def test_projecao_e_reparo_condicional(self):
        geom = box(-57, -16, -56.99, -15.99)
        p = Patch("2020-01-01", 123, 1, 1, geom)
        dados_proj, reparados = projetar_patches([p])
        self.assertEqual(reparados, 0)
        self.assertTrue(p.geometria.is_valid)
        self.assertFalse(p.reparado_apos_projecao)
        self.assertTrue(dados_proj["crs"].startswith("LAEA"))

    def test_id_dinamico_e_entrada_inalterada(self):
        geom1 = box(-57, -16, -56.99, -15.99)
        geom2 = box(-57, -16, -56.98, -15.98)
        colecao = {"type": "FeatureCollection", "features": [
            self.feicao(geom1, "2020-01-01", 1, 1, 1, incendio=777),
            self.feicao(geom2, "2020-01-02", 1, 1, 4, incendio=777),
        ]}
        with TemporaryDirectory() as diretorio:
            entrada = Path(diretorio) / "evento_777.geojson"
            saida = Path(diretorio) / "saida"
            entrada.write_text(json.dumps(colecao), encoding="utf-8")
            original = hashlib.sha256(entrada.read_bytes()).hexdigest()
            resultado = executar(entrada, saida)
            self.assertEqual(resultado["id_incendio"], 777)
            self.assertEqual(resultado["numero_datas"], 2)
            self.assertTrue((saida / "metricas_patches_777.csv").exists())
            self.assertTrue((saida / "sensibilidade_contato_777.csv").exists())
            self.assertEqual(hashlib.sha256(entrada.read_bytes()).hexdigest(), original)

    def test_regressao_dados_reais_se_disponiveis(self):
        raiz = Path(__file__).resolve().parents[1]
        dados = raiz / "dados/estudo_caso_24340828/P1_componentes_24340828.geojson"
        if not dados.exists():
            self.skipTest("Arquivo do estudo de caso nao disponivel")
        with TemporaryDirectory() as pasta:
            resumo = executar(dados, Path(pasta))
            self.assertEqual(resumo["numero_registros_patch_data"], 978)
            self.assertEqual(resumo["numero_datas"], 57)
            self.assertEqual(resumo["geometrias_reparadas_apos_projecao"], 0)
            self.assertEqual(resumo["contatos_entre_patches"]["contatos_pontuais"], 657)
            self.assertEqual(resumo["contatos_entre_patches"]["contatos_por_borda"], 0)
            self.assertEqual(resumo["contatos_entre_patches"]["sobreposicoes_maiores_1m2"], 0)
            self.assertTrue(isclose(resumo["area_final_laea_km2"], 981.2908540,
                                    abs_tol=1e-3))
            self.assertEqual(len(list(Path(pasta).glob("*.csv"))), 3)
            self.assertEqual(
                resumo["sensibilidade_contato_vetorial"]["soma_grupos_por_contato_patch_data"],
                369
            )


if __name__ == "__main__":
    unittest.main()
