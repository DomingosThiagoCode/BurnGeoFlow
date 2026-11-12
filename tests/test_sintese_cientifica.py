"""Testes da síntese exploratória com dados sintéticos, sem GEE ou QGIS."""
from __future__ import annotations

import csv
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from burngeoflow.relatorios.sintese_caso import (
    sintetizar, numero, ranking,
)

EVENTO = 24340828


def gravar_csv(caminho: Path, linhas: list[dict]):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)


def fixture(raiz: Path) -> tuple[Path, Path]:
    dados = raiz / "dados" / f"estudo_caso_{EVENTO}"
    dados.mkdir(parents=True)
    p1 = dados / f"P1_componentes_{EVENTO}.geojson"
    p2 = dados / f"P2_regiao_movel_{EVENTO}.geojson"
    p1.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    p2.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    e5 = raiz / "resultados" / "etapa5"
    e6 = raiz / "resultados" / "etapa6"
    e5.mkdir(parents=True)
    e6.mkdir(parents=True)
    resumo5 = {
        "id_incendio": EVENTO, "observacoes": 3, "transicoes": 2,
        "periodo_inicio": "2020-09-17", "periodo_fim": "2020-09-19",
        "numero_fases_bic": 2,
        "sha256_p1": sha256(p1.read_bytes()).hexdigest(),
        "sha256_p2": sha256(p2.read_bytes()).hexdigest(),
    }
    resumo6 = {
        "id_incendio": EVENTO, "observacoes": 3, "transicoes": 2,
        "dias_com_contagem_sensivel": 1,
        "n_cenarios_fases": 5, "alteracoes_fases": 2,
        "dias_sobreposicao_p1_acima_1m2": ["2020-09-18"],
        "sobreposicao_p1_maxima_m2": 1.246868,
        "transicoes_com_perda_area_acumulada_acima_1m2": [],
        "status_cientifico": "revisao_geometrica_pendente",
        "validacao_externa_concluida": False,
    }
    (e5 / f"resumo_etapa5_{EVENTO}.json").write_text(
        json.dumps(resumo5), encoding="utf-8",
    )
    (e6 / f"resumo_validacao_{EVENTO}.json").write_text(
        json.dumps(resumo6), encoding="utf-8",
    )
    gravar_csv(e5 / f"serie_diaria_integrada_{EVENTO}.csv", [
        {
            "id_incendio": EVENTO,
            "data": d, "numero_patches": n,
            "area_total_laea_km2": a, "p2_area_laea_km2": b,
            "dominancia_cobertura_p2_pct": 100 * b / a,
        }
        for d, n, a, b in [
            ("2020-09-17", 5, 10, 5),
            ("2020-09-18", 3, 20, 13),
            ("2020-09-19", 1, 30, 15),
        ]
    ])
    gravar_csv(e5 / f"transicoes_integradas_{EVENTO}.csv", [
        {
            "id_incendio": EVENTO,
            "data_anterior": "2020-09-17",
            "data_atual": "2020-09-18",
            "dias_intervalo": 1,
            "taxa_nova_evento_km2_dia": 10.0,
            "area_nova_evento_km2": 10.0,
            "p2_incremento_geometrico_km2": 8.0,
            "p2_incremento_ja_queimado_km2": 5.0,
            "p2_incremento_nova_area_evento_km2": 3.0,
            "fracao_incremento_p2_ja_queimado_pct": 62.5,
            "eventos_convergencia": 2,
            "igt_concentracao_direcional": 0.8,
            "tr_azimute_centroide_graus": 20.0,
            "igt_azimute_ponderado_graus": 30.0,
        },
        {
            "id_incendio": EVENTO,
            "data_anterior": "2020-09-18",
            "data_atual": "2020-09-19",
            "dias_intervalo": 1,
            "taxa_nova_evento_km2_dia": 10.0,
            "area_nova_evento_km2": 10.0,
            "p2_incremento_geometrico_km2": 2.0,
            "p2_incremento_ja_queimado_km2": 0.5,
            "p2_incremento_nova_area_evento_km2": 1.5,
            "fracao_incremento_p2_ja_queimado_pct": 25.0,
            "eventos_convergencia": 1,
            "igt_concentracao_direcional": 0.2,
            "tr_azimute_centroide_graus": 20.0,
            "igt_azimute_ponderado_graus": 90.0,
        },
    ])
    return p1, p2


class TesteSinteseCientifica(unittest.TestCase):
    def test_cria_dossie_com_resultados_e_alertas_sem_reatribuicao_causal(self):
        with TemporaryDirectory() as d:
            raiz = Path(d)
            p1, p2 = fixture(raiz)
            antes = (sha256(p1.read_bytes()).hexdigest(),
                     sha256(p2.read_bytes()).hexdigest())
            saida = raiz / "resultados" / "sintese_cientifica"
            resultado = sintetizar(raiz, EVENTO, saida)
            resumo = resultado["resumo"]
            self.assertEqual(resumo["observacoes"], 3)
            self.assertEqual(resumo["transicoes"], 2)
            self.assertEqual(resumo["numero_convergencias_geometricas"], 3)
            self.assertAlmostEqual(
                resumo["soma_incorporacao_ja_queimada_p2_km2"], 5.5
            )
            self.assertAlmostEqual(
                resumo["fracao_incremento_prequeimado_pct"], 55.0
            )
            self.assertEqual(
                resumo["top_taxa_area_nova_evento"][0]["fim"],
                "2020-09-18",
            )
            self.assertEqual(
                resumo["direcoes_tr_igt_comparaveis_criterio_exploratorio"], 1
            )
            self.assertAlmostEqual(
                resumo["mediana_diferenca_angular_tr_igt_filtrada_graus"], 10
            )
            self.assertEqual(
                resumo["dias_sobreposicao_p1_pendentes"], ["2020-09-18"]
            )
            self.assertFalse(resumo["validacao_externa_concluida"])
            md = (saida / f"sintese_cientifica_{EVENTO}.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("não é a área única total", md)
            self.assertIn("revisao_geometrica_pendente", md)
            self.assertIn("0,25 km²", md)
            self.assertTrue(
                (saida / f"indicadores_sintese_{EVENTO}.json").is_file()
            )
            self.assertIn(
                "validação externa: não",
                (saida / f"resumo_para_chat_{EVENTO}.txt").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertEqual(
                antes,
                (sha256(p1.read_bytes()).hexdigest(),
                 sha256(p2.read_bytes()).hexdigest()),
            )

    def test_rejeita_dados_de_outra_versao_sem_reprocessar(self):
        with TemporaryDirectory() as d:
            raiz = Path(d)
            p1, _ = fixture(raiz)
            p1.write_text('{"changed":true}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                sintetizar(raiz, EVENTO, raiz / "saida")
            self.assertFalse((raiz / "saida").exists())

    def test_rejeita_intervalo_com_data_incoerente(self):
        with TemporaryDirectory() as d:
            raiz = Path(d)
            fixture(raiz)
            caminho = (raiz / "resultados" / "etapa5"
                       / f"transicoes_integradas_{EVENTO}.csv")
            with caminho.open(encoding="utf-8", newline="") as f:
                linhas = list(csv.DictReader(f))
            linhas[1]["data_anterior"] = "2020-09-17"
            gravar_csv(caminho, linhas)
            with self.assertRaisesRegex(ValueError, "Transições"):
                sintetizar(raiz, EVENTO, raiz / "saida")

    def test_rejeita_somas_p2_que_nao_fecham(self):
        with TemporaryDirectory() as d:
            raiz = Path(d)
            fixture(raiz)
            caminho = (raiz / "resultados" / "etapa5"
                       / f"transicoes_integradas_{EVENTO}.csv")
            with caminho.open(encoding="utf-8", newline="") as f:
                linhas = list(csv.DictReader(f))
            linhas[0]["p2_incremento_ja_queimado_km2"] = "500"
            gravar_csv(caminho, linhas)
            with self.assertRaisesRegex(ValueError, "não fecham"):
                sintetizar(raiz, EVENTO, raiz / "saida")

    def test_dados_nao_finitos_nao_geram_ranking(self):
        self.assertIsNone(numero({"a": ""}, "a", opcional=True))
        with self.assertRaisesRegex(ValueError, "não finito"):
            ranking([{
                "a": "nan", "data_atual": "2020-01-01",
            }], "a")


if __name__ == "__main__":
    unittest.main()
