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

    def test_json_atomico(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "teste.json"
            salvar_json(p, {"ok": True})
            self.assertTrue(json.loads(p.read_text())["ok"])
            self.assertFalse((Path(d) / "teste.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
