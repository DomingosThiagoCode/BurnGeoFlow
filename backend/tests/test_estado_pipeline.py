"""API de checkpoints para eventos parciais, sem login GEE e sem mutações."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient
from backend.app.main import criar_app
from backend.app.services.estado_pipeline import inspecionar_pipeline
from burngeoflow.processamento.metodologia_v2 import VERSAO
from executar_pipeline import digest


class TestEstadoPipeline(unittest.TestCase):
    def test_endpoint_sem_arquivos_nao_gera_erro_ou_consulta_gee(self):
        with TemporaryDirectory() as tmp, TestClient(
            criar_app(dados_dir=Path(tmp))
        ) as client:
            r=client.get("/api/events/24194371/pipeline-status")
            self.assertEqual(r.status_code,200,r.text)
            obj=r.json()
            self.assertFalse(obj["pronto_para_reprocessamento_integral_v2"])
            self.assertEqual(obj["dados"]["p1_local"]["estado"],"ausente")
            self.assertEqual(obj["dados"]["bruto_gee_p1"]["estado"],"ausente")
            self.assertEqual(obj["preprocessamento_v2"]["estado"],"pendente")
            self.assertEqual(len(obj["etapas"]),8)
            self.assertEqual(client.get("/api/events/0/pipeline-status").status_code,422)

    def test_insumo_perdido_e_etapa_legada_invalidada(self):
        with TemporaryDirectory() as tmp:
            base=Path(tmp)
            raiz=base/"24194371"
            dados=raiz/"dados"/"estudo_caso_24194371"
            dados.mkdir(parents=True)
            p1=dados/"P1_componentes_24194371.geojson"
            p2=dados/"P2_regiao_movel_24194371.geojson"
            p1.write_text("P1-bruto","utf-8")
            p2.write_text("P2-bruto","utf-8")
            (dados/"brutos_gee").mkdir()
            (dados/"brutos_gee"/p1.name).write_text("raw","utf-8")
            manifesto={
                "id_incendio":24194371,
                "entradas_sha256":{"p1":digest(p1),"p2":digest(p2)},
                "etapas":{
                    "validar":{"status":"concluido","codigo_sha256":"HASH_INVALIDO"},
                    "auditar":{"status":"falha"},
                    "paisagem":{"status":"concluido"},
                },
            }
            (raiz/"execucao.json").write_text(json.dumps(manifesto),"utf-8")
            out=inspecionar_pipeline(24194371,base)
            self.assertEqual(out["dados"]["bruto_gee_p1"]["estado"],"disponivel")
            estados={e["nome"]:e["estado"] for e in out["etapas"]}
            self.assertEqual(estados["validar"],"artefato_perdido")
            self.assertEqual(estados["auditar"],"erro")
            self.assertEqual(estados["paisagem"],"artefato_perdido")
            self.assertTrue(out["alertas"])
            p1.write_text("P1-alterado","utf-8")
            out=inspecionar_pipeline(24194371,base)
            self.assertFalse(out["entradas_compativeis_manifesto_legado"])

    def test_preprocessamento_v2_somente_marcado_com_hash_compativel(self):
        with TemporaryDirectory() as tmp:
            base=Path(tmp)
            dados=base/"24340828"/"dados"/"estudo_caso_24340828"
            dados.mkdir(parents=True)
            p1=dados/"P1_componentes_24340828.geojson"
            p2=dados/"P2_regiao_movel_24340828.geojson"
            p1.write_text("origem","utf-8")
            p2.write_text("outra","utf-8")
            pasta=dados/"derivados_v2"/VERSAO
            pasta.mkdir(parents=True)
            for tipo in ("P1_componentes","P2_regiao_movel"):
                (pasta/f"{tipo}_24340828.geojson").write_text("gerado","utf-8")
            (pasta/"auditoria_cobertura_p1.json").write_text(
                '{"componentes":[]}', "utf-8"
            )
            codigo=(Path(__file__).resolve().parents[2] /
                    "burngeoflow"/"processamento"/"metodologia_v2.py")
            md={"metodologia":VERSAO,"sha256_p1_origem":digest(p1),
                "codigo_sha256":digest(codigo),
                "sha256_p1_v2":digest(pasta/"P1_componentes_24340828.geojson"),
                "sha256_p2_v2":digest(pasta/"P2_regiao_movel_24340828.geojson"),
                "sha256_auditoria_cobertura_p1":digest(
                    pasta/"auditoria_cobertura_p1.json"
                ),
                "datas_p1":57,"datas_p2":37,
                "primeira_data_p2":"2020-08-27"}
            manifesto = pasta / "manifesto_metodologia.json"
            manifesto.write_text(json.dumps(md), "utf-8")
            out=inspecionar_pipeline(24340828,base)
            self.assertEqual(out["preprocessamento_v2"]["estado"],
                             "preprocessado_nao_integrado")
            self.assertFalse(out["pronto_para_reprocessamento_integral_v2"])
            progresso = pasta / "estado_preprocessamento.json"
            progresso.write_text("{", "utf-8")
            out = inspecionar_pipeline(24340828, base)
            self.assertEqual(out["preprocessamento_v2"]["estado"], "erro_manifesto")
            progresso.unlink()

            for chave in (
                "sha256_p1_origem", "codigo_sha256",
                "sha256_p1_v2", "sha256_p2_v2",
                "sha256_auditoria_cobertura_p1"
            ):
                with self.subTest(chave=chave):
                    manifesto.write_text(json.dumps({**md, chave: None}), "utf-8")
                    out = inspecionar_pipeline(24340828, base)
                    self.assertEqual(
                        out["preprocessamento_v2"]["estado"], "proveniencia_incompleta"
                    )
            manifesto.write_text(json.dumps(md), "utf-8")

            def digest_com_artefato_desaparecido(path):
                if path == pasta / "P2_regiao_movel_24340828.geojson":
                    raise FileNotFoundError(path)
                return digest(path)

            with patch("backend.app.services.estado_pipeline.digest",
                       side_effect=digest_com_artefato_desaparecido):
                out = inspecionar_pipeline(24340828, base)
                self.assertEqual(out["preprocessamento_v2"]["estado"], "artefato_modificado")

            (pasta/"auditoria_cobertura_p1.json").unlink()
            out=inspecionar_pipeline(24340828,base)
            self.assertEqual(out["preprocessamento_v2"]["estado"],
                             "artefato_perdido")
            (pasta/"auditoria_cobertura_p1.json").write_text(
                '{"componentes":[]}',"utf-8"
            )
            (pasta/"P2_regiao_movel_24340828.geojson").write_text("corrompido","utf-8")
            out=inspecionar_pipeline(24340828,base)
            self.assertEqual(out["preprocessamento_v2"]["estado"],
                             "artefato_modificado")
            p1.write_text("modificado","utf-8")
            out=inspecionar_pipeline(24340828,base)
            self.assertEqual(out["preprocessamento_v2"]["estado"],
                             "origem_alterada")


if __name__=="__main__":
    unittest.main()
