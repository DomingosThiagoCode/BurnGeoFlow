"""Teste de contrato do orquestrador sem GEE ou dados externos."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import json
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from executar_pipeline import (ErroPipeline, Etapa, preparar_dados,
                               definir_etapas, salvar_json, executar)
from burngeoflow.aquisicao.dados_referencia import git_hash


class TestePipeline(unittest.TestCase):
    def test_git_hash(self):
        self.assertEqual(git_hash(b"test content\n"),
                         "d670460b4b4aece5915caf5c68d12f560a9fe3e4")

    def test_entradas_pareadas(self):
        with TemporaryDirectory() as d:
            with self.assertRaisesRegex(ErroPipeline, "--p1 e --p2"):
                preparar_dados(1, Path(d), Path(d) / "x.json", None, False)

    def test_ordem(self):
        with TemporaryDirectory() as d:
            raiz = Path(d)
            nomes = [e.nome for e in definir_etapas(2, raiz,
                     raiz / "a.json", raiz / "b.json")]
            self.assertEqual(nomes, [
                "validar", "auditar", "regularizar_diagnostico", "paisagem",
                "linhagens", "tr_igt", "integrar", "robustez"
            ])

    def test_erro_subprocesso_aparece_no_terminal_e_log_e_preservado(self):
        with TemporaryDirectory() as d:
            raiz = Path(d)
            output = raiz / "saida.json"
            etapa = Etapa(
                nome="tr_igt", comando=["python", "modulo"],
                artefatos=(output,),
            )
            resultado = SimpleNamespace(
                returncode=1, stdout="",
                stderr="FALHA: Area nova TR/IGT nao confere em 2020-09-01 "
                       "-> 2020-09-02: divergencia=2.500000 m2",
            )
            with patch(
                "executar_pipeline.preparar_dados",
                return_value=(raiz/"p1.geojson", raiz/"p2.geojson",
                              {"p1": "a", "p2": "b"}),
            ), patch("executar_pipeline.definir_etapas", return_value=[etapa]), \
                 patch("executar_pipeline.subprocess.run", return_value=resultado):
                with self.assertRaisesRegex(ErroPipeline, "divergencia=2.500000 m2"):
                    executar(1, saida=raiz)
            log = raiz / "logs/tr_igt.log"
            self.assertTrue(log.is_file())
            self.assertIn("2020-09-02", log.read_text(encoding="utf-8"))
            manifesto = json.loads((raiz/"execucao.json").read_text())
            self.assertEqual(manifesto["etapas"]["tr_igt"]["status"], "falha")

    def test_artefatos_de_auditoria_sao_obrigatorios_para_reuso(self):
        with TemporaryDirectory() as d:
            raiz = Path(d)
            etapas = {e.nome: e for e in definir_etapas(
                24340828, raiz, raiz/"a.geojson", raiz/"b.geojson"
            )}
            caminhos4 = {p.name for p in etapas["tr_igt"].artefatos}
            caminhos5 = {p.name for p in etapas["integrar"].artefatos}
            self.assertIn(
                "resumo_consolidado_tr_igt_24340828.json", caminhos4
            )
            self.assertIn("resumo_regiao_movel_24340828.json", caminhos4)
            self.assertIn("resumo_incrementos_24340828.json", caminhos4)
            self.assertIn("resumo_etapa5_24340828.json", caminhos5)
            self.assertIn("auditoria_p1_sobreposicoes_24340828.json", caminhos5)

    def test_reuso_depende_de_codigo_e_predecessor(self):
        with TemporaryDirectory() as d:
            raiz = Path(d)
            a = raiz/"a.json"
            b = raiz/"b.json"
            e1 = Etapa("validar", ["python", "validar"], (a,))
            e2 = Etapa("auditar", ["python", "auditar"], (b,))
            ids = {"validar": "v1", "auditar": "v1"}
            executadas = []

            def simular(cmd, **kwargs):
                executadas.append(cmd[-1])
                destino = a if cmd[-1] == "validar" else b
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text("ok", encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("executar_pipeline.preparar_dados",
                       return_value=(raiz/"p1.json", raiz/"p2.json",
                                     {"p1":"a", "p2":"b"})), \
                 patch("executar_pipeline.definir_etapas",
                       return_value=(e1, e2)), \
                 patch("executar_pipeline.assinatura_codigo",
                       side_effect=lambda nome: ids[nome]), \
                 patch("executar_pipeline.subprocess.run",
                       side_effect=simular):
                executar(1, saida=raiz)
                self.assertEqual(executadas, ["validar", "auditar"])
                executar(1, saida=raiz)
                self.assertEqual(executadas, ["validar", "auditar"])
                ids["validar"] = "v2"
                executar(1, saida=raiz)
                self.assertEqual(
                    executadas, ["validar", "auditar", "validar", "auditar"]
                )
            manifesto = json.loads((raiz/"execucao.json").read_text())
            self.assertEqual(
                manifesto["etapas"]["validar"]["codigo_sha256"], "v2"
            )
            self.assertEqual(
                manifesto["etapas"]["auditar"]["codigo_sha256"], "v1"
            )

    def test_json_atomico(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "teste.json"
            salvar_json(p, {"ok": True})
            self.assertTrue(json.loads(p.read_text())["ok"])
            self.assertFalse((Path(d) / "teste.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
