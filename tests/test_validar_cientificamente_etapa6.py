"""Etapa 6: verificacao analitica e regressao real do dossie."""
from __future__ import annotations
from datetime import date,timedelta
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from validar_cientificamente_etapa6 import (
    angular, direcoes, contatos, fases_sensiveis, executar)

class TestesSinteticos(unittest.TestCase):
    def test_angulo_circular(self):
        self.assertEqual(angular(350,10),20)
        self.assertEqual(angular(10,350),20)
        self.assertEqual(angular(20,200),180)
        self.assertIsNone(angular(None,10))

    def test_sensibilidade_concentracao(self):
        t=[dict(id_incendio="1",data_anterior="2020-01-01",
            data_atual="2020-01-02",igt_concentracao_direcional="0.4",
            tr_azimute_centroide_graus="350",igt_azimute_ponderado_graus="10")]
        rows,ag=direcoes(t)
        self.assertEqual(len(rows),5)
        self.assertEqual([x["n_comparaveis"] for x in ag],[1,1,0,0,0])
        self.assertEqual(ag[0]["mediana_diferenca_graus"],20)

    def test_contato_preserva_patch_original(self):
        d=[dict(data="2020-01-01",id_incendio="1",
                numero_patches="3",dominancia_maior_patch_pct="50")]
        tab={("2020-01-01",):dict(numero_patches_original="3",
             numero_grupos_por_contato_vetorial="2",dominancia_original_pct="50",
             dominancia_apos_agrupar_contatos_pct="75",pares_contato_pontual="1")}
        result=contatos(tab,d)[0]
        self.assertAlmostEqual(result["reducao_pct"],100/3)
        self.assertEqual(result["diferenca_dominancia_pp"],25)
        self.assertEqual(d[0]["numero_patches"],"3")

    def test_sensibilidade_fases_no_minimo_2(self):
        inicio=date(2020,8,1)
        dados=[]
        for i in range(35):
            valor=(i*2 if i<12 else 24+(i-12)*7 if i<24
                   else 108+(i-24)*1)
            dados.append(dict(data=str(inicio+timedelta(days=i)),
                              area_total_laea_km2=float(valor)))
        c=fases_sensiveis(dados)
        self.assertGreaterEqual(len(c),5)
        self.assertEqual(c[0]["cenario"],"base")
        self.assertTrue(all(1<=x["n_fases"]<=3 for x in c))

class TesteReal(unittest.TestCase):
    def test_evidencias_reais_e_dados_intactos(self):
        raiz=Path(__file__).resolve().parents[1]
        p=raiz/"dados/estudo_caso_24340828"
        a=p/"P1_componentes_24340828.geojson"
        b=p/"P2_regiao_movel_24340828.geojson"
        if not (a.exists() and b.exists()):
            self.skipTest("GeoJSON originais indisponiveis")
        h1,h2=sha256(a.read_bytes()).hexdigest(),sha256(b.read_bytes()).hexdigest()
        with TemporaryDirectory() as d:
            resumo=executar(raiz,24340828,Path(d))
            self.assertEqual((resumo["observacoes"],resumo["transicoes"]),(57,56))
            self.assertEqual(resumo["dias_com_contagem_sensivel"],56)
            self.assertEqual(resumo["pares_pontuais"],657)
            self.assertEqual(resumo["lacunas"],3)
            self.assertAlmostEqual(resumo["soma_incorporacao_ja_queimada_km2"],
                                   195.958449956,places=4)
            self.assertGreaterEqual(resumo["geojson_feicoes"],8)
            self.assertFalse(resumo["validacao_externa_concluida"])
            self.assertTrue((Path(d)/"relatorio_validacao_24340828.md").exists())
            feature=json.loads((Path(d)/"revisao_qgis_24340828.geojson").read_text())
            self.assertTrue(all(x["properties"]["id_incendio"]==24340828
                                for x in feature["features"]))
        self.assertEqual((h1,h2),(sha256(a.read_bytes()).hexdigest(),
                                  sha256(b.read_bytes()).hexdigest()))

if __name__=="__main__":
    unittest.main()
