"""Pré-processamento científico v2 sem acesso ao GEE nem alteração dos brutos."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shapely.geometry import Polygon, box, mapping

from burngeoflow.processamento.metodologia_v2 import (
    ErroMetodologia, VERSAO, reconstruir,
)


def feat(data, rank, geom, n=1, id_=24340828):
    return {
        "type":"Feature", "geometry":mapping(geom),
        "properties":{
            "data":data,"rank":rank,"id_incendio":id_,
            "area_km2":1.0,"numero_componentes":n,"area_total_km2":float(n),
        },
    }


def escrever(path, features):
    path.write_text(json.dumps({
        "type":"FeatureCollection","features":features,
    }),encoding="utf-8")


class TestMetodologiaV2(unittest.TestCase):
    def test_autointersecao_apos_projecao_suspende_e_preserva_entrada(self):
        # Quadrilátero artificial. As cordas projetadas cruzam junto à aresta
        # quase coincidente, embora a geometria em WGS84 seja válida.
        poligono = Polygon([(0, 40), (0.004, 40 + 3e-8),
                            (0.015, 40 + 2e-6), (0.02, 40)])
        self.assertTrue(poligono.is_valid)
        with TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            origem = raiz / "p1.geojson"
            # A segunda feição mantém o centro da projeção em (0, 0).
            escrever(origem, [feat("2020-01-01", 1, poligono, 2),
                              feat("2020-01-01", 2, box(-0.02, -40 - 2e-6, 0, -39), 2)])
            entrada = origem.read_bytes()
            derivados = raiz / "derivados"
            with self.assertRaisesRegex(ErroMetodologia, "inválida após projeção"):
                reconstruir(origem, derivados)
            pasta = derivados / VERSAO
            diagnostico = json.loads((pasta / "diagnostico_bloqueio.json").read_text())
            self.assertEqual(diagnostico["detalhes"]["rank"], 1)
            self.assertFalse((pasta / "manifesto_metodologia.json").exists())
            self.assertEqual(origem.read_bytes(), entrada)

    def test_p1_contato_pontual_e_p2_retro_sem_substituir_entrada(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            origem=root/"P1_original.geojson"
            # Dia inicial: A e C se encostam somente num vértice, B isolado
            # e maior. No fim, A torna-se dominante. A regra retrospectiva
            # seleciona sua ancestral, não o maior patch da primeira data.
            features=[
                feat("2020-01-01",1,box(0,0,1,1),3),
                feat("2020-01-01",2,box(5,0,7,2),3),
                feat("2020-01-01",3,box(1,1,2,2),3),
                feat("2020-01-02",1,box(0,0,3,3),2),
                feat("2020-01-02",2,box(5,0,7,2),2),
                feat("2020-01-03",1,box(0,0,8,3),1),
            ]
            escrever(origem,features)
            antes=hashlib.sha256(origem.read_bytes()).hexdigest()
            result=reconstruir(origem,root/"derivados")
            self.assertEqual(result["metodologia"],VERSAO)
            self.assertEqual(result["datas_p1"],3)
            self.assertEqual(result["datas_p2"],3)
            self.assertEqual(hashlib.sha256(origem.read_bytes()).hexdigest(),antes)
            folder=root/"derivados"/VERSAO
            p1=json.loads((folder/"P1_componentes_24340828.geojson").read_text())
            p2=json.loads((folder/"P2_regiao_movel_24340828.geojson").read_text())
            self.assertEqual(len(p1["features"]),5)
            self.assertEqual(len(p2["features"]),3)
            balanco=json.loads((folder/"balanco_expansao_p2.json").read_text())
            self.assertEqual(len(balanco["transicoes"]),2)
            self.assertEqual(resultado["transicoes_balanco_d005"],2)
            self.assertTrue(all(x["dias_intervalo"]==1 for x in balanco["transicoes"]))
            self.assertTrue(all(x["erro_particao_expansao_m2"]>=0
                                for x in balanco["transicoes"]))
            d1=[e for e in p1["features"] if e["properties"]["data"]=="2020-01-01"]
            self.assertEqual(len(d1),2)  # contato somente por vértice agrupa
            self.assertIn([1,3],[e["properties"]["ranks_origem"] for e in d1])
            self.assertEqual(p2["features"][0]["properties"]["rank"],2)
            self.assertEqual(p2["features"][-1]["properties"]["rank"],1)

    def test_p2_sem_ancestral_nao_inventa_mais_datas(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            origem=root/"p1.geojson"
            escrever(origem,[
                feat("2020-01-01",1,box(0,0,1,1)),
                feat("2020-01-02",1,box(5,5,7,7)),
            ])
            r=reconstruir(origem,root/"derivados")
            self.assertEqual(r["datas_p1"],2)
            self.assertEqual(r["datas_p2"],1)
            self.assertEqual(r["primeira_data_p2"],"2020-01-02")
            self.assertEqual(r["transicoes_balanco_d005"],0)
            balanco=json.loads(
                (root/"derivados"/VERSAO/"balanco_expansao_p2.json").read_text()
            )
            self.assertEqual(balanco["transicoes"],[])

    def test_sobreposicao_intradata_conserva_cobertura_e_registra_evidencia(self):
        # Dois patches que se sobrepõem são um único componente D-002.
        # A sobreposição não pode duplicar a área ou escolher um "dono".
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            origem=root/"p1.geojson"
            escrever(origem,[
                feat("2020-01-01",1,box(0,0,2,2),2),
                feat("2020-01-01",2,box(1,1,3,3),2),
            ])
            original=origem.read_bytes()
            resultado=reconstruir(origem,root/"derivados")
            pasta=root/"derivados"/VERSAO
            auditoria=json.loads((pasta/"auditoria_cobertura_p1.json").read_text())
            p1=json.loads((pasta/"P1_componentes_24340828.geojson").read_text())
            self.assertEqual(resultado["datas_p1"],1)
            self.assertEqual(resultado["componentes_com_residuo_positivo"],1)
            self.assertTrue(auditoria["requer_revisao_qualitativa"])
            self.assertEqual(len(auditoria["componentes"]),1)
            self.assertEqual(auditoria["componentes"][0]["ranks_origem"],[1,2])
            self.assertGreater(auditoria["componentes"][0]["area_contada_repetidamente_m2"],0)
            self.assertEqual(len(p1["features"]),1)
            self.assertEqual(p1["features"][0]["properties"]["ranks_origem"],[1,2])
            self.assertEqual(p1["features"][0]["properties"]["numero_componentes"],1)
            self.assertLess(
                p1["features"][0]["properties"]["area_km2"]*1e6,
                auditoria["componentes"][0]["area_somada_m2"]
            )
            self.assertEqual(origem.read_bytes(),original)
            self.assertFalse((pasta/"diagnostico_bloqueio.json").exists())

    def test_cobertura_de_disjuntos_nao_inventa_sobreposicao(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            origem=root/"p1.geojson"
            escrever(origem,[
                feat("2020-01-01",1,box(0,0,1,1),2),
                feat("2020-01-01",2,box(3,3,4,4),2),
            ])
            resultado=reconstruir(origem,root/"derivados")
            auditoria=json.loads(
                (root/"derivados"/VERSAO/"auditoria_cobertura_p1.json").read_text()
            )
            self.assertEqual(resultado["componentes_com_residuo_positivo"],0)
            self.assertEqual(auditoria["componentes"],[])


if __name__=="__main__":
    unittest.main()
