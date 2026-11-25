"""Teste offline de batch GEE. Nenhuma credencial Google é utilizada."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from burngeoflow.aquisicao.exportacao_batch import (
    ErroLote, asset_id, materializar, limpar_apos_validacao, aguardar,
)
from burngeoflow.aquisicao.earth_engine import adquirir, ErroAquisicao


def fake_gee():
    tasks = {}
    counter = [0]

    class TaskFake:
        def __init__(self, asset):
            counter[0] += 1
            self.id = f"T-{counter[0]}"
            self.asset = asset

        def start(self):
            tasks[self.id] = "COMPLETED"

    def exportar(*, collection, description, assetId):
        return TaskFake(assetId)

    def status(taskid):
        return [{"id": taskid, "state": tasks[taskid]}]

    ee = SimpleNamespace(
        batch=SimpleNamespace(
            Export=SimpleNamespace(
                table=SimpleNamespace(toAsset=Mock(side_effect=exportar))
            )
        ),
        data=SimpleNamespace(
            getTaskStatus=Mock(side_effect=status),
            deleteAsset=Mock(),
        ),
        FeatureCollection=lambda ident: ("asset", ident),
    )
    return ee, tasks


def dados_fake(id_=24340828):
    geometria = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
    }
    p1 = {"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": geometria,
        "properties": {
            "id_incendio": id_, "ano_dataset": 2020,
            "data": "2020-01-01", "rank": 1, "area_km2": 1,
            "numero_componentes": 1, "area_total_km2": 1,
        }
    }]}
    p2 = deepcopy(p1)
    p2["features"][0]["properties"].update({
        "rank_global": 1, "delta_area_km2": 0,
        "delta_area_total_km2": 0,
        "metodo_continuidade": "inicial_maior_area",
    })
    return p1, p2


class BatchAssetsTest(unittest.TestCase):
    def test_asset_id_nunca_cruza_outro_projeto(self):
        self.assertEqual(
            asset_id("meu-projeto-gee", 24340828, 2020, "123456abcdef", "p1"),
            "projects/meu-projeto-gee/assets/bgf_24340828_2020_123456abcdef_p1",
        )
        for projeto in ("", "../../outro", "a", "PRJ !"):
            with self.assertRaises(ErroLote):
                asset_id(projeto, 1, 2020, "123456abcdef", "p1")

    def test_materializa_e_retoma_sem_novas_tarefas(self):
        ee, _ = fake_gee()
        with TemporaryDirectory() as t:
            kw = {
                "projeto": "meu-projeto-gee", "incendio": 24340828, "ano": 2020,
                "assinatura": "globfire-v2:24340828:2020", "pasta": Path(t),
                "informar": lambda _: None,
            }
            a, estado_path = materializar(ee, {"P1": "p1", "P2": "p2"}, **kw)
            b, _ = materializar(ee, {"P1": "p1", "P2": "p2"}, **kw)
            self.assertEqual(a, b)
            self.assertEqual(ee.batch.Export.table.toAsset.call_count, 2)
            checkpoint = json.loads(estado_path.read_text())
            self.assertEqual(
                {x["estado"] for x in checkpoint["tarefas"].values()}, {"COMPLETED"}
            )
            limpar_apos_validacao(ee, a, estado_path, informar=lambda _: None)
            self.assertEqual(ee.data.deleteAsset.call_count, 2)
            self.assertTrue(json.loads(estado_path.read_text())["finalizado"])

    def test_erro_remoto_nao_apaga_asset(self):
        ee, states = fake_gee()
        original = ee.batch.Export.table.toAsset.side_effect
        def criar(*, collection, description, assetId):
            task = original(collection=collection, description=description, assetId=assetId)
            if collection == "p2":
                start_original = task.start
                def start():
                    start_original()
                    states[task.id] = "FAILED"
                task.start = start
            return task
        ee.batch.Export.table.toAsset.side_effect = criar
        with TemporaryDirectory() as t:
            with self.assertRaisesRegex(ErroLote, "FAILED"):
                materializar(
                    ee, {"P1": "p1", "P2": "p2"},
                    projeto="meu-projeto-gee", incendio=5, ano=2020,
                    assinatura="x", pasta=Path(t), informar=lambda _: None,
                )
            self.assertEqual(ee.data.deleteAsset.call_count, 0)
            checkpoint = json.loads(
                (Path(t) / "estado_batch_5.json").read_text()
            )
            self.assertIn("task_id", checkpoint["tarefas"]["P2"])

    def test_espera_limite_local_nao_cancela_tarefa(self):
        ee, _ = fake_gee()
        ee.data.getTaskStatus = Mock(return_value=[{"state": "RUNNING"}])
        clock = iter([0, 1, 4, 8, 12])
        with self.assertRaisesRegex(ErroLote, "retomar"):
            aguardar(
                ee, "P1", {"task_id": "t-abc"},
                informar=lambda _: None, intervalo_s=2, espera_max_s=5,
                dormir=lambda _: None, relogio=lambda: next(clock),
            )
        ee.data.deleteAsset.assert_not_called()

    def test_falha_reutilizacao_assinatura_divergente(self):
        ee, _ = fake_gee()
        with TemporaryDirectory() as t:
            materializar(
                ee, {"P1": "p1", "P2": "p2"},
                projeto="meu-projeto-gee", incendio=5, ano=2020,
                assinatura="versao-1", pasta=Path(t), informar=lambda _: None,
            )
            with self.assertRaisesRegex(ErroLote, "incompatível"):
                materializar(
                    ee, {"P1": "p1", "P2": "p2"},
                    projeto="meu-projeto-gee", incendio=5, ano=2020,
                    assinatura="versao-2", pasta=Path(t), informar=lambda _: None,
                )


class TesteIntegracaoModoAuto(unittest.TestCase):
    @patch("burngeoflow.aquisicao.earth_engine.limpar_apos_validacao")
    @patch("burngeoflow.aquisicao.earth_engine.materializar")
    @patch("burngeoflow.aquisicao.earth_engine.obter_geojson")
    @patch("burngeoflow.aquisicao.earth_engine.construir_produtos")
    @patch("burngeoflow.aquisicao.earth_engine.localizar_evento")
    def test_auto_exporta_57_dias_em_batch(
        self, localizar, construir, baixar, materializar_mock, limpar,
    ):
        p1, p2 = dados_fake()
        localizar.return_value = ("evento", 2020, 947)
        construir.return_value = ("p1_expr", "p2_expr", 57)
        baixar.side_effect = [p1, p2]
        materializar_mock.return_value = (
            {"P1": "projects/meu-projeto-gee/assets/asset_p1",
             "P2": "projects/meu-projeto-gee/assets/asset_p2"},
            Path("estado.json"),
        )
        ee, _ = fake_gee()
        with TemporaryDirectory() as t:
            a, b, meta = adquirir(
                24340828, Path(t), ano=2020,
                projeto="meu-projeto-gee", ee_modulo=ee,
                informar=lambda _: None,
            )
            self.assertTrue(a.is_file() and b.is_file())
            self.assertEqual(meta["estrategia_gee"], "lote")
            self.assertEqual(baixar.call_count, 2)
            self.assertEqual(baixar.call_args_list[0].args[1][0], "asset")
            materializar_mock.assert_called_once()
            limpar.assert_called_once()

    @patch("burngeoflow.aquisicao.earth_engine.limpar_apos_validacao")
    @patch("burngeoflow.aquisicao.earth_engine.materializar")
    @patch("burngeoflow.aquisicao.earth_engine.obter_geojson")
    @patch("burngeoflow.aquisicao.earth_engine.construir_produtos")
    @patch("burngeoflow.aquisicao.earth_engine.localizar_evento")
    def test_auto_troca_para_batch_apos_timeout(
        self, localizar, construir, baixar, materializar_mock, limpar,
    ):
        p1, p2 = dados_fake()
        localizar.return_value = ("evento", 2020, 947)
        construir.return_value = ("p1_expr", "p2_expr", 1)
        baixar.side_effect = [
            ErroAquisicao("Computation timed out."),
            p1, p2,
        ]
        materializar_mock.return_value = (
            {"P1": "projects/meu-projeto-gee/assets/asset_p1",
             "P2": "projects/meu-projeto-gee/assets/asset_p2"},
            Path("estado.json"),
        )
        ee, _ = fake_gee()
        with TemporaryDirectory() as t:
            _, _, meta = adquirir(
                24340828, Path(t), ano=2020,
                projeto="meu-projeto-gee", ee_modulo=ee,
                informar=lambda _: None,
            )
            self.assertEqual(meta["estrategia_gee"], "lote")
            self.assertEqual(baixar.call_count, 3)
            limpar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
