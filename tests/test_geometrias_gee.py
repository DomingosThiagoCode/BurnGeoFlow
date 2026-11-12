"""Regressão offline: geometria mista, dados brutos e cache de páginas GEE."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest

from burngeoflow.aquisicao.geometrias import (
    ErroGeometria, normalizar_produtos, diagnosticar
)
from burngeoflow.aquisicao.earth_engine import (
    ErroAquisicao, obter_geojson, preparar_e_publicar,
    reprocessar_brutos, pastas_brutas, salvar_json_atomico,
)
from burngeoflow.validacao.produtos import verificar
from executar_pipeline import main

POLIGONO = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
}
LINHA = {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}
PONTO = {"type": "Point", "coordinates": [0, 0]}


def amostra() -> tuple[dict, dict]:
    data = "2020-08-09"
    propriedades = {
        "id_incendio": 24340828, "ano_dataset": 2020, "data": data,
        "rank": 1, "area_km2": 2.0, "numero_componentes": 1,
        "area_total_km2": 2.0, "proporcao_area_pct": 100.0,
        "eh_maior": True,
    }
    p1 = {"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": deepcopy(POLIGONO),
        "properties": deepcopy(propriedades),
    }]}
    extra = deepcopy(propriedades)
    extra.update({
        "rank_global": 1,
        "ordem_temporal": 1,
        "delta_area_km2": 0.0, "delta_area_total_km2": 0.0,
        "delta_num_componentes": 0,
        "metodo_continuidade": "inicial_maior_area",
    })
    p2 = {"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": deepcopy(POLIGONO),
        "properties": extra,
    }]}
    return p1, p2


class TesteNormalizacao(unittest.TestCase):
    def test_geometrycollection_com_poligono_e_linha(self):
        p1, p2 = amostra()
        p1["features"][0]["geometry"] = {
            "type": "GeometryCollection",
            "geometries": [deepcopy(POLIGONO), deepcopy(LINHA)],
        }
        novo_p1, novo_p2, rel = normalizar_produtos(p1, p2)
        self.assertEqual(novo_p1["features"][0]["geometry"], POLIGONO)
        self.assertEqual(novo_p2["features"][0]["properties"]["rank"], 1)
        self.assertEqual(len(rel["geometrias_convertidas"]), 1)
        self.assertEqual(rel["sem_area_excluidos"], [])
        self.assertEqual(p1["features"][0]["geometry"]["type"], "GeometryCollection")

    def test_nao_area_zero_excluida_com_auditoria_e_ranks(self):
        p1, p2 = amostra()
        rejeitada = deepcopy(p1["features"][0])
        rejeitada["geometry"] = deepcopy(PONTO)
        rejeitada["properties"].update({
            "rank": 2, "area_km2": 0.0,
            "numero_componentes": 2, "proporcao_area_pct": 0.0,
            "eh_maior": False,
        })
        p1["features"][0]["properties"]["numero_componentes"] = 2
        p2["features"][0]["properties"]["numero_componentes"] = 2
        p1["features"].append(rejeitada)
        novo_p1, novo_p2, rel = normalizar_produtos(p1, p2)
        self.assertEqual(len(novo_p1["features"]), 1)
        self.assertEqual(len(rel["sem_area_excluidos"]), 1)
        self.assertEqual(novo_p2["features"][0]["properties"]["numero_componentes"], 1)
        self.assertTrue(rel["ranks_atualizados"])
        with TemporaryDirectory() as temp:
            p1_path, p2_path = Path(temp)/"p1.json", Path(temp)/"p2.json"
            p1_path.write_text(json.dumps(novo_p1))
            p2_path.write_text(json.dumps(novo_p2))
            self.assertEqual(verificar(p1_path, p2_path)["datas"], 1)

    def test_nao_area_com_area_positiva_exige_revisao(self):
        p1, p2 = amostra()
        p1["features"][0]["geometry"] = deepcopy(LINHA)
        with self.assertRaisesRegex(ErroGeometria, "area positiva"):
            normalizar_produtos(p1, p2)

    def test_diagnostico_identifica_indice_original(self):
        p1, p2 = amostra()
        p1["features"].append(deepcopy(p1["features"][0]))
        p1["features"][1]["geometry"] = deepcopy(LINHA)
        diagnostico = diagnosticar(p1, "P1")
        self.assertEqual(diagnostico["feicoes_para_revisao"][0]["indice"], 1)
        self.assertEqual(diagnostico["feicoes_para_revisao"][0]["tipo"], "LineString")


class TestePersistencia(unittest.TestCase):
    def test_persiste_brutos_antes_da_validacao(self):
        p1, p2 = amostra()
        p1["features"][0]["geometry"] = deepcopy(LINHA)
        with TemporaryDirectory() as temp:
            pasta = Path(temp)
            with self.assertRaises(ErroAquisicao):
                preparar_e_publicar(pasta, 24340828, p1, p2,
                                   informar=lambda x: None)
            a, b, diag = pastas_brutas(pasta, 24340828)
            self.assertTrue(a.is_file())
            self.assertTrue(b.is_file())
            self.assertTrue(diag.is_file())
            dados = json.loads(diag.read_text(encoding="utf-8"))
            self.assertEqual(dados["status"], "requer_analise")
            self.assertEqual(dados["P1"]["feicoes_para_revisao"][0]["indice"], 0)
            self.assertFalse((pasta/"P1_componentes_24340828.geojson").exists())

    def test_reprocessamento_offline_sem_acessar_gee(self):
        p1, p2 = amostra()
        with TemporaryDirectory() as temp:
            pasta = Path(temp)
            a, b, _ = pastas_brutas(pasta, 24340828)
            salvar_json_atomico(a, p1)
            salvar_json_atomico(b, p2)
            caminhos = reprocessar_brutos(
                24340828, pasta, informar=lambda x: None)
            self.assertTrue(caminhos[0].exists())
            self.assertTrue(caminhos[1].exists())
            self.assertEqual(caminhos[2]["origem"], "brutos_gee_em_disco")


class TesteCachePaginas(unittest.TestCase):
    def test_reusa_pagina_sem_requisitar_novamente(self):
        p1, _ = amostra()
        with TemporaryDirectory() as temp:
            pasta = Path(temp)
            fetch = Mock(return_value={"features": p1["features"]})
            ee = SimpleNamespace(data=SimpleNamespace(computeFeatures=fetch))
            kwargs = {
                "pasta_paginas": pasta,
                "chave_cache": "asset:ano:id:alg:P1",
                "informar": lambda x: None,
            }
            novo = obter_geojson(ee, "consulta", **kwargs)
            self.assertEqual(len(novo["features"]), 1)
            fetch.reset_mock()
            reuso = obter_geojson(ee, "consulta", **kwargs)
            self.assertEqual(reuso, novo)
            fetch.assert_not_called()

    def test_cache_incompativel_rejeitado(self):
        p1, _ = amostra()
        with TemporaryDirectory() as temp:
            pasta = Path(temp)
            ee = SimpleNamespace(data=SimpleNamespace(
                computeFeatures=Mock(return_value={"features": p1["features"]})))
            obter_geojson(ee, "consulta", pasta_paginas=pasta,
                          chave_cache="versao1", informar=lambda x: None)
            with self.assertRaisesRegex(ErroAquisicao, "incompatível"):
                obter_geojson(ee, "consulta", pasta_paginas=pasta,
                              chave_cache="versao2", informar=lambda x: None)

    def test_retorna_paginas_salvas_e_continua_na_pendente(self):
        p1, _ = amostra()
        f = p1["features"][0]
        with TemporaryDirectory() as temp:
            pasta = Path(temp)
            fetch = Mock(side_effect=[
                {"features": [f], "next_page_token": "proxima"},
                RuntimeError("conexao"),
            ])
            ee = SimpleNamespace(data=SimpleNamespace(computeFeatures=fetch))
            with self.assertRaises(ErroAquisicao):
                obter_geojson(ee, "consulta", pasta_paginas=pasta,
                              chave_cache="constante", informar=lambda x: None)
            self.assertTrue((pasta/"pagina_00001.json").is_file())
            fetch2 = Mock(return_value={"features": [f]})
            ee2 = SimpleNamespace(data=SimpleNamespace(computeFeatures=fetch2))
            resultado = obter_geojson(ee2, "consulta", pasta_paginas=pasta,
                                     chave_cache="constante",
                                     informar=lambda x: None)
            self.assertEqual(len(resultado["features"]), 2)
            self.assertEqual(fetch2.call_args.args[0]["pageToken"], "proxima")


class TesteModoBrutos(unittest.TestCase):
    @patch("executar_pipeline.executar")
    @patch("burngeoflow.aquisicao.earth_engine.reprocessar_brutos")
    def test_cli_somente_brutos_nao_usa_gee(self, mock_reprocessar, mock_exec):
        mock_reprocessar.return_value = (
            Path("p1.json"), Path("p2.json"),
            {"id_incendio": 24340828, "datas": 57}
        )
        with TemporaryDirectory() as temp:
            retorno = main([
                "--id", "24340828", "--origem", "brutos",
                "--somente-aquisicao", "--saida", temp
            ])
        self.assertEqual(retorno, 0)
        mock_exec.assert_not_called()
        mock_reprocessar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
