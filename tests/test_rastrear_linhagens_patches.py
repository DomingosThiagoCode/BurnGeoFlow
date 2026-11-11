"""Casos sinteticos e regressao da Etapa 3 (linhagens temporais P1)."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from shapely.geometry import box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from burngeoflow.analises.paisagem import Patch  # noqa: E402
from burngeoflow.processamento.linhagens import (  # noqa: E402
    analisar_linhagens, eventos_bipartidos, executar, vincular_por_area,
)


def sintetico(data: str, rank: int, geometria: object, incendio=123) -> Patch:
    p = Patch(data, incendio, rank, geometria.area / 1e6, geometria)
    p.area_m2, p.perimetro_m = geometria.area, geometria.length
    return p


class VinculosTests(unittest.TestCase):
    def test_continuacao_preserva_linhagem_e_cria_patch_sem_predecessor(self):
        patches = [
            sintetico("2020-01-01", 1, box(0, 0, 10, 10)),
            sintetico("2020-01-03", 1, box(0, 0, 12, 10)),
            sintetico("2020-01-03", 2, box(12, 10, 20, 20)),
        ]
        linhas, vinculos, eventos, resumos, relatorio = analisar_linhagens(patches)
        self.assertEqual(len(linhas), 3)
        self.assertEqual(len(vinculos), 1)
        self.assertEqual(vinculos[0]["rank_anterior"], 1)
        self.assertEqual(vinculos[0]["rank_atual"], 1)
        self.assertEqual(linhas[0]["id_linhagem"], linhas[1]["id_linhagem"])
        self.assertNotEqual(linhas[1]["id_linhagem"], linhas[2]["id_linhagem"])
        self.assertEqual(linhas[2]["numero_antecessores"], 0)
        self.assertEqual(linhas[2]["tipo_entrada"], "surgimento_sem_sobreposicao")
        self.assertEqual(linhas[0]["tipo_entrada"], "linha_de_base")
        self.assertEqual(linhas[-1]["tipo_saida"], "sem_observacao_posterior")
        self.assertEqual(resumos[0]["dias_intervalo"], 2)
        self.assertEqual(resumos[0]["eventos_surgimento_sem_sobreposicao"], 1)
        self.assertEqual(relatorio["numero_linhagens_conservadoras"], 2)
        self.assertEqual(len(eventos), 2)

    def test_convergencia_duas_areas_para_uma_cria_linhagem_nova(self):
        patches = [
            sintetico("2020-01-01", 1, box(0, 0, 10, 10)),
            sintetico("2020-01-01", 2, box(15, 0, 25, 10)),
            sintetico("2020-01-02", 1, box(0, 0, 25, 10)),
        ]
        linhas, vinculos, eventos, resumos, _ = analisar_linhagens(patches)
        self.assertEqual(len(vinculos), 2)
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]["tipo_evento"], "convergencia")
        self.assertEqual(eventos[0]["numero_patches_anteriores"], 2)
        self.assertEqual(eventos[0]["numero_patches_atuais"], 1)
        self.assertEqual(linhas[2]["linhagens_antecessoras"], "L000001;L000002")
        self.assertEqual(linhas[2]["id_linhagem"], "L000003")
        self.assertEqual(resumos[0]["eventos_convergencia"], 1)
        self.assertAlmostEqual(
            resumos[0]["porcentagem_area_anterior_vinculada"], 100
        )

    def test_toque_apenas_por_vertice_nao_gera_vinculo(self):
        ant = [sintetico("2020-01-01", 1, box(0, 0, 10, 10))]
        nov = [sintetico("2020-01-02", 1, box(10, 10, 20, 20))]
        arestas, pais, filhos, contatos = vincular_por_area(ant, nov)
        self.assertEqual(arestas, [])
        self.assertEqual(pais[1], [])
        self.assertEqual(filhos[1], [])
        self.assertEqual(contatos["pontual"], 1)
        self.assertEqual(
            [t for t, _, _ in eventos_bipartidos(ant, nov, pais, filhos)],
            ["sem_sucessor", "surgimento_sem_sobreposicao"],
        )

    def test_contato_por_borda_nao_gera_vinculo(self):
        ant = [sintetico("2020-01-01", 1, box(0, 0, 10, 10))]
        nov = [sintetico("2020-01-02", 1, box(10, 0, 20, 10))]
        arestas, _, _, contatos = vincular_por_area(ant, nov)
        self.assertEqual(arestas, [])
        self.assertEqual(contatos["linear"], 1)

    def test_divergencia_gera_duas_linhagens_sem_arbitrio(self):
        patches = [
            sintetico("2020-01-01", 1, box(0, 0, 10, 10)),
            sintetico("2020-01-02", 1, box(0, 0, 4, 10)),
            sintetico("2020-01-02", 2, box(6, 0, 10, 10)),
        ]
        linhas, _, eventos, resumos, _ = analisar_linhagens(patches)
        self.assertEqual(eventos[0]["tipo_evento"], "divergencia")
        self.assertEqual(resumos[0]["eventos_divergencia"], 1)
        self.assertEqual(linhas[0]["tipo_saida"], "multiplos_sucessores")
        self.assertEqual(
            [p["id_linhagem"] for p in linhas],
            ["L000001", "L000002", "L000003"]
        )

    def test_reorganizacao_muitos_para_muitos(self):
        patches = [
            sintetico("2020-01-01", 1, box(0, 0, 10, 10)),
            sintetico("2020-01-01", 2, box(10, 0, 20, 10)),
            sintetico("2020-01-02", 1, box(0, 0, 20, 5)),
            sintetico("2020-01-02", 2, box(0, 5, 20, 10)),
        ]
        _, vinculos, eventos, resumos, _ = analisar_linhagens(patches)
        self.assertEqual(len(vinculos), 4)
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]["tipo_evento"], "reorganizacao")
        self.assertEqual(resumos[0]["eventos_reorganizacao"], 1)

    def test_limiar_numerico_pode_ser_variado(self):
        ant = [sintetico("2020-01-01", 1, box(0, 0, 10, 10))]
        nov = [sintetico("2020-01-02", 1, box(9.95, 0, 11, 1))]
        self.assertEqual(len(vincular_por_area(ant, nov, 1)[0]), 0)
        self.assertEqual(len(vincular_por_area(ant, nov, 0)[0]), 1)
        with self.assertRaises(ValueError):
            vincular_por_area(ant, nov, float("nan"))
        with self.assertRaises(ValueError):
            vincular_por_area(ant, nov, -1)

    def test_sobreposicao_de_patches_na_mesma_data_e_rejeitada(self):
        ant = [sintetico("2020-01-01", 1, box(0, 0, 10, 10))]
        nov = [sintetico("2020-01-02", 1, box(0, 0, 10, 10)),
               sintetico("2020-01-02", 2, box(0, 0, 10, 10))]
        with self.assertRaisesRegex(ValueError, "soma das intersecoes"):
            vincular_por_area(ant, nov)

    def test_data_unica_e_linha_de_base(self):
        patches = [sintetico("2020-01-01", 1, box(0, 0, 10, 10))]
        linhas, vinculos, eventos, transicoes, resumo = analisar_linhagens(patches)
        self.assertEqual(len(linhas), 1)
        self.assertEqual(len(vinculos), 0)
        self.assertEqual(len(eventos), 0)
        self.assertEqual(len(transicoes), 0)
        self.assertIsNone(linhas[0]["numero_sucessores"])
        self.assertEqual(resumo["numero_transicoes_observadas"], 0)


class ArquivosTests(unittest.TestCase):
    def test_id_dinamico_e_input_intocado(self):
        duas = [box(-57, -16, -56.99, -15.99),
                box(-57, -16, -56.98, -15.98)]
        features = []
        for i, geom in enumerate(duas):
            features.append({
                "type": "Feature", "geometry": mapping(geom),
                "properties": {
                    "id_incendio": 777, "data": f"2020-01-0{i+1}",
                    "rank": 1, "area_km2": i + 1,
                    "numero_componentes": 1, "area_total_km2": i + 1,
                }
            })
        with TemporaryDirectory() as temp:
            path = Path(temp) / "entrada.geojson"
            path.write_text(json.dumps({
                "type": "FeatureCollection", "features": features
            }), encoding="utf-8")
            inicial = hashlib.sha256(path.read_bytes()).hexdigest()
            saida = Path(temp) / "resultados"
            resumo = executar(path, saida)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), inicial)
            self.assertEqual(resumo["id_incendio"], 777)
            self.assertEqual(resumo["sha256_p1"], inicial)
            self.assertTrue((saida / "resumo_linhagens_777.json").exists())
            with (saida / "linhagens_patches_777.csv").open() as f:
                linhas = list(csv.DictReader(f))
            self.assertEqual(len(linhas), 2)
            geojson = json.loads((saida / "convergencias_para_qgis_777.geojson")
                                 .read_text(encoding="utf-8"))
            self.assertEqual(geojson["features"], [])

    def test_regressao_caso_real_quando_disponivel(self):
        entrada = (Path(__file__).resolve().parents[1] / "dados" /
                   "estudo_caso_24340828" / "P1_componentes_24340828.geojson")
        if not entrada.exists():
            self.skipTest("GeoJSON de referencia nao esta presente")
        with TemporaryDirectory() as temp:
            resumo = executar(entrada, Path(temp))
            camada_qgis = json.loads(
                (Path(temp) / "convergencias_para_qgis_24340828.geojson")
                .read_text(encoding="utf-8")
            )
            with (Path(temp) / "eventos_topologicos_24340828.csv").open() as f:
                eventos = list(csv.DictReader(f))
            with (Path(temp) / "resumo_transicoes_24340828.csv").open() as f:
                transicoes = list(csv.DictReader(f))
        self.assertEqual(resumo["numero_registros_p1"], 978)
        self.assertEqual(resumo["numero_datas"], 57)
        self.assertEqual(resumo["numero_transicoes_observadas"], 56)
        self.assertEqual(resumo["numero_vinculos_area"], 963)
        self.assertEqual(resumo["eventos_por_tipo"]["convergencia"], 72)
        self.assertEqual(len(camada_qgis["features"]), 72)
        self.assertEqual(camada_qgis["features"][0]["type"], "Feature")
        originais = json.loads(entrada.read_text(encoding="utf-8"))["features"]
        por_chave = {
            (f["properties"]["data"], f["properties"]["rank"]): f["geometry"]
            for f in originais
        }
        for f in camada_qgis["features"]:
            props = f["properties"]
            self.assertEqual(
                f["geometry"], por_chave[(props["data_atual"], props["rank_atual"])]
            )
        # O grafo nao pode perder nem duplicar vertices em cada transicao.
        for t in transicoes:
            do_par = [e for e in eventos
                      if e["data_anterior"] == t["data_anterior"]
                      and e["data_atual"] == t["data_atual"]]
            self.assertEqual(
                sum(int(e["numero_patches_anteriores"]) for e in do_par),
                int(t["patches_anteriores"]),
            )
            self.assertEqual(
                sum(int(e["numero_patches_atuais"]) for e in do_par),
                int(t["patches_atuais"]),
            )
        convergencia_10_11 = [
            e for e in eventos if e["data_anterior"] == "2020-09-10"
            and e["data_atual"] == "2020-09-11"
            and e["tipo_evento"] == "convergencia"
        ]
        self.assertEqual(len(convergencia_10_11), 1)
        self.assertEqual(int(convergencia_10_11[0]["numero_patches_anteriores"]), 21)
        self.assertEqual(resumo["eventos_por_tipo"]["continuacao"], 685)
        self.assertEqual(resumo["eventos_por_tipo"]["surgimento_sem_sobreposicao"], 219)
        self.assertGreater(resumo["menor_retencao_area_anterior_pct"], 99.99)
        self.assertEqual(len(resumo["lacunas_temporais"]), 3)


if __name__ == "__main__":
    unittest.main()
