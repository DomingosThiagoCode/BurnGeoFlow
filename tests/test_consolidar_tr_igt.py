"""Testes conceituais e regressao do fecho TR x IGT em Python."""
import importlib.util
from pathlib import Path
import sys
import unittest

import pyproj
from shapely.geometry import box

spec = importlib.util.spec_from_file_location(
    'fecho', Path(__file__).resolve().parents[1]/'scripts/consolidar_tr_igt.py')
fecho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fecho)


def dados(d0='2020-01-01', d1='2020-01-02', dias=1, nova=1, perda=0):
    tr = {'id_incendio':'1','data_anterior':d0,'data_atual':d1,
          'dias_intervalo':str(dias), 'area_nova_p2_km2':str(nova),
          'area_perdida_p2_km2':str(perda), 'azimute_centroide_graus':'20',
          'deslocamento_centroide_km':'2',
          **{f'avanco_{a}_km':'0.1' for a in ('norte','sul','leste','oeste')}}
    igt = {'id_incendio':'1','data_anterior':d0,'data_atual':d1,
           'dias_intervalo':str(dias), 'area_nova_km2':str(nova),
           'area_perdida_km2':str(perda), 'numero_componentes_incremento':'2',
           'azimute_medio_ponderado_graus':'350', 'concentracao_direcional':'0.7'}
    return tr, igt


class ConsolidacaoTestes(unittest.TestCase):
    def test_angulos_cruzando_zero(self):
        self.assertEqual(fecho.angulo_minimo(350, 10), 20)
        self.assertEqual(fecho.angulo_minimo(10, 350), 20)
        self.assertEqual(fecho.angulo_minimo(0,180), 180)
        self.assertIsNone(fecho.angulo_minimo(None, 200))

    def test_compara_area_taxa_lacuna_e_direcao(self):
        tr, igt = dados('2020-01-01','2020-01-03',2,3.2,0)
        out = fecho.comparar_linhas(tr,igt,n_reducao=0,soma_reducao_erro_m2=0)
        self.assertEqual(out['dias_intervalo'],2)
        self.assertTrue(out['lacuna_temporal'])
        self.assertAlmostEqual(out['igt_area_nova_km2_por_dia'],1.6)
        self.assertEqual(out['diferenca_angular_tr_igt_graus'],30)

    def test_area_divergente_e_rejeitada(self):
        tr,igt=dados()
        igt['area_nova_km2']='1.02'
        with self.assertRaisesRegex(ValueError,'Area nova'):
            fecho.comparar_linhas(tr,igt,n_reducao=0,soma_reducao_erro_m2=0)

    def test_chave_incompativel_rejeitada(self):
        tr,igt=dados()
        igt['id_incendio']='99'
        with self.assertRaisesRegex(ValueError,'discordam'):
            fecho.comparar_linhas(tr,igt,n_reducao=0,soma_reducao_erro_m2=0)

    def test_reducao_direcao_componente_para_centroide(self):
        inv=pyproj.Transformer.from_crs('EPSG:3857','EPSG:4326',always_xy=True)
        geod=pyproj.Geod(ellps='WGS84')
        inicial=box(0,0,2000,1000)
        atual=box(1000,0,2000,1000)
        partes,area,erro=fecho.direcoes_reducao(
            inicial,atual,inv,geod,evento=1,dia0='2020-01-01',dia1='2020-01-02')
        self.assertEqual(len(partes),1)
        self.assertAlmostEqual(area,1)
        self.assertLess(erro,1e-8)
        self.assertTrue(80 < partes[0]['azimute_reducao_graus'] < 100)

    def test_reducao_vazia(self):
        inv=pyproj.Transformer.from_crs('EPSG:3857','EPSG:4326',always_xy=True)
        geod=pyproj.Geod(ellps='WGS84')
        partes,area,erro=fecho.direcoes_reducao(
            box(0,0,1000,1000),box(0,0,2000,1000),inv,geod,
            evento=1,dia0='2020-01-01',dia1='2020-01-02')
        self.assertEqual(partes,[])
        self.assertEqual((area,erro),(0,0))


class RegressaoGeoJSON(unittest.TestCase):
    def test_pantanal_integracao_real(self):
        import json
        import tempfile
        import subprocess
        raiz = Path(__file__).resolve().parents[1]
        p1 = raiz/'dados/estudo_caso_24340828/P1_componentes_24340828.geojson'
        p2 = raiz/'dados/estudo_caso_24340828/P2_regiao_movel_24340828.geojson'
        if not (p1.exists() and p2.exists()):
            self.skipTest('GeoJSON P1/P2 nao encontrados neste ambiente')
        with tempfile.TemporaryDirectory() as pasta:
            r=subprocess.run([sys.executable,str(raiz/'scripts/consolidar_tr_igt.py'),
                              str(p1),str(p2),'--saida',pasta],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr[-3500:])
            obj=json.loads((Path(pasta)/'resumo_consolidado_tr_igt_24340828.json').read_text())
            self.assertEqual((obj['datas'],obj['transicoes']),(57,56))
            self.assertEqual(obj['correspondencia_p1_p2'],'57/57')
            self.assertAlmostEqual(obj['area_nova_total_km2'],949.843488705,places=4)
            self.assertTrue((Path(pasta)/'comparacao_tr_igt_24340828.csv').exists())
            self.assertTrue((Path(pasta)/'componentes_reducao_24340828.csv').exists())


if __name__=='__main__':
    unittest.main()
