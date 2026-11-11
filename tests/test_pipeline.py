"""Teste de contrato do orquestrador sem GEE ou dados externos."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from executar_pipeline import ErroPipeline, preparar_dados, definir_etapas, salvar_json
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

    def test_json_atomico(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "teste.json"
            salvar_json(p, {"ok": True})
            self.assertTrue(json.loads(p.read_text())["ok"])
            self.assertFalse((Path(d) / "teste.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
