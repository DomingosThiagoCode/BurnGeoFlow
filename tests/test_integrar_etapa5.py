"""Etapa 5: decomposicao geometrica, segmentacao e integracao real."""
from __future__ import annotations

import csv
from datetime import date,timedelta
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from shapely.geometry import box
from shapely.ops import unary_union

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from burngeoflow.analises.integracao import (decompor_transicao, segmentar_fases,
                            marcar_fases, executar, conferir_proximo,
                            ler_tabela, valor)


class MatematicaAnalitica(unittest.TestCase):
    def test_fusao_reune_area_ja_queimada_sem_confundir_com_area_nova(self):
        prev_principal=box(0,0,10,10)
        prev_secundario=box(20,0,30,10)
        anterior=unary_union([prev_principal,prev_secundario])
        atual=box(0,0,30,10)  # 100 m2 ponte nova + 100 m2 ilha antiga
        r=decompor_transicao(anterior,atual,prev_principal,atual)
        self.assertAlmostEqual(r["area_nova_evento_km2"],100/1e6)
        self.assertAlmostEqual(r["p2_incremento_geometrico_km2"],200/1e6)
        self.assertAlmostEqual(r["p2_incremento_ja_queimado_km2"],100/1e6)
        self.assertAlmostEqual(r["p2_incremento_nova_area_evento_km2"],100/1e6)
        self.assertAlmostEqual(r["nova_area_fora_p2_km2"],0)
        self.assertLess(r["desvio_fechamento_p2_m2"],1e-8)

    def test_expansao_simples_nao_e_incorporacao(self):
        antes=box(0,0,10,10)
        depois=box(0,0,15,10)
        r=decompor_transicao(antes,depois,antes,depois)
        self.assertAlmostEqual(r["p2_incremento_ja_queimado_km2"],0)
        self.assertAlmostEqual(r["p2_incremento_nova_area_evento_km2"],50/1e6)

    def test_crescimento_fora_do_p2(self):
        antes=box(0,0,10,10)
        segundo=box(20,20,30,30)
        hoje=unary_union([antes,segundo])
        r=decompor_transicao(antes,hoje,antes,antes)
        self.assertAlmostEqual(r["p2_incremento_geometrico_km2"],0)
        self.assertAlmostEqual(r["nova_area_fora_p2_km2"],100/1e6)

    def test_areas_reduzidas_registradas_sem_negativar_nova(self):
        antes=box(0,0,20,10)
        depois=box(5,0,20,10)
        r=decompor_transicao(antes,depois,antes,depois)
        self.assertAlmostEqual(r["area_perdida_evento_km2"],50/1e6)
        self.assertAlmostEqual(r["area_nova_evento_km2"],0)

    def test_fases_com_tres_tendencias_distintas(self):
        origem=date(2020,8,1)
        y=[]
        for x in range(30):
            y.append(2*x if x<10 else (20+15*(x-10) if x<20 else 170+2*(x-20)))
        linhas=[{"data":str(origem+timedelta(days=x)),"area_total_laea_km2":v}
                for x,v in enumerate(y)]
        fases,breaks=segmentar_fases(linhas,min_obs=7,max_fases=3)
        self.assertEqual(len(fases),3)
        self.assertEqual(breaks,[0,10,20,30])
        marcar_fases(linhas,fases,breaks)
        self.assertEqual(linhas[15]["fase_descritiva"],"F2")

    def test_rejeita_comparacao_numerica_divergente(self):
        with self.assertRaisesRegex(ValueError,"Inconsistencia"):
            conferir_proximo(1.,2.,"area")
        with self.assertRaisesRegex(ValueError,"numero nao finito"):
            valor({"area":"nan"},"area")

    def test_detecta_linhas_csv_duplicadas(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"t.csv"
            p.write_text("data,val\n2020-01-01,2\n2020-01-01,3\n",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"duplicada"):
                ler_tabela(p,campos_chave=("data",))


class RegressaoEstudoCaso(unittest.TestCase):
    def test_integracao_cientifica_do_id_24340828(self):
        raiz=Path(__file__).resolve().parents[1]
        p1=raiz/"dados/estudo_caso_24340828/P1_componentes_24340828.geojson"
        p2=raiz/"dados/estudo_caso_24340828/P2_regiao_movel_24340828.geojson"
        if not p1.exists() or not p2.exists():
            self.skipTest("P1/P2 reais ausentes neste ambiente")
        h1=sha256(p1.read_bytes()).hexdigest()
        h2=sha256(p2.read_bytes()).hexdigest()
        with TemporaryDirectory() as d:
            resumo=executar(raiz,24340828,Path(d))
            self.assertEqual((resumo["observacoes"],resumo["transicoes"]),(57,56))
            self.assertEqual(resumo["total_convergencias_geometricas"],72)
            self.assertAlmostEqual(resumo["area_total_final_laea_km2"],981.290854021,places=5)
            self.assertAlmostEqual(resumo["area_p2_final_laea_km2"],951.341001069,places=5)
            self.assertLess(resumo["maximo_erro_fechamento_m2"],1)
            self.assertEqual(resumo["transicoes_com_lacunas"],3)
            self.assertTrue(resumo["soma_incorporacao_area_ja_queimada_no_p2_km2"]>0)
            data=resumo["transicao_2020_09_11"]
            self.assertIsNotNone(data)
            self.assertAlmostEqual(data["area_nova_evento_km2"],107.824000175,places=4)
            self.assertAlmostEqual(data["p2_incremento_geometrico_km2"],212.434113491,places=4)
            self.assertTrue(data["p2_incremento_ja_queimado_km2"]>100)
            self.assertEqual(data["numero_patches_anterior"],42)
            self.assertEqual(data["numero_patches_atual"],25)
            with (Path(d)/"transicoes_integradas_24340828.csv").open() as f:
                trans=list(csv.DictReader(f))
            self.assertEqual(len(trans),56)
            self.assertTrue((Path(d)/"01_areas_p1_p2.png").stat().st_size>5000)
            self.assertTrue((Path(d)/"mapa_2020-09-11.png").stat().st_size>5000)
            self.assertTrue((Path(d)/"relatorio_interpretativo_24340828.md").exists())
        self.assertEqual((h1,h2),(sha256(p1.read_bytes()).hexdigest(),
                                  sha256(p2.read_bytes()).hexdigest()))


if __name__=="__main__":
    unittest.main()
