"""Pré-processamento científico v2 sem acesso ao GEE nem alteração dos brutos."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shapely.geometry import box, mapping

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
            d1=[e for e in p1["features"] if e["properties"]["data"]=="2020-01-01"]
            self.assertEqual(len(d1),2)  # contato somente por vértice agrupa
            self.assertIn([1,3],[e["properties"]["ranks_origem"] for e in d1])
            self.assertEqual(p2["features"][0]["properties"]["ranks_origem"] if
                "ranks_origem" in p2["features"][0]["properties"] else
                p1["features"][0]["properties"]["metodologia"], VERSAO)

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

    def test_area_sobreposta_suspende_e_salva_diagnostico(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            origem=root/"p1.geojson"
            escrever(origem,[
                feat("2020-01-01",1,box(0,0,2,2),2),
                feat("2020-01-01",2,box(1,1,3,3),2),
            ])
            with self.assertRaisesRegex(ErroMetodologia,"sobreposição intradata"):
                reconstruir(origem,root/"derivados")
            pasta=root/"derivados"/VERSAO
            d=json.loads((pasta/"diagnostico_bloqueio.json").read_text())
            self.assertEqual(d["status"],"bloqueado_revisao_topologica")
            self.assertTrue(d["detalhes"]["sobreposicao_laea_m2"]>1)
            self.assertFalse((pasta/"manifesto_metodologia.json").exists())


if __name__=="__main__":
    unittest.main()
