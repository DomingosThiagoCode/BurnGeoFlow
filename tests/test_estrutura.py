"""Contratos da arquitetura, sem autenticação GEE."""
from pathlib import Path
import unittest
from shapely.geometry import box
from burngeoflow.processamento.componentes import agrupar_por_data
from burngeoflow.processamento.conectividade import grupos_conectados
from burngeoflow.aquisicao.earth_engine import selecionar_evento, ErroAquisicao
from burngeoflow.relatorios.saida import resumo_etapas


class TesteEstrutura(unittest.TestCase):
    def test_vertice_e_conectado(self):
        self.assertEqual(grupos_conectados(
            [box(0, 0, 1, 1), box(1, 1, 2, 2), box(10, 10, 11, 11)]
        ), [[0, 1], [2]])

    def test_conectividade_transitiva(self):
        self.assertEqual(grupos_conectados(
            [box(0, 0, 1, 1), box(2, 2, 3, 3), box(1, 1, 2, 2)]
        ), [[0, 1, 2]])

    def test_ordem_temporal_e_rank(self):
        fc = {"type": "FeatureCollection", "features": [
            {"properties": {"data": "2020-01-02", "rank": 2}},
            {"properties": {"data": "2020-01-01", "rank": 1}},
            {"properties": {"data": "2020-01-02", "rank": 1}}
        ]}
        grupos = agrupar_por_data(fc)
        self.assertEqual(list(grupos), ["2020-01-01", "2020-01-02"])
        self.assertEqual([f["properties"]["rank"] for f in grupos["2020-01-02"]], [1, 2])

    def test_ano_invalido(self):
        with self.assertRaises(ErroAquisicao):
            selecionar_evento(None, 1, 2025)

    def test_resumo_etapas(self):
        resumo = resumo_etapas({"id_incendio": 3, "etapas": {
            "a": {"status": "concluido"}, "b": {"status": "falha"}
        }})
        self.assertEqual(resumo, {
            "id_incendio": 3, "concluidas": ["a"], "com_falha": ["b"]
        })

    def test_sem_diretorios_de_experimentacao_legados(self):
        raiz = Path(__file__).resolve().parents[1]
        # scripts/ agora contém ferramentas de diagnóstico do produto,
        # não os experimentos SQL/GEE legados removidos em 2026.
        for nome in ["sql", "gee"]:
            self.assertFalse((raiz / nome).exists(), f"Legado {nome} no produto")


if __name__ == "__main__":
    unittest.main()
