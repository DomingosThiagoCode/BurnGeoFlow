import tempfile
import unittest
from datetime import datetime, timezone
from burngeoflow.aquisicao.catalogo import agregar, janela, catalogo

AOI = {"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}

class TestCatalogo(unittest.TestCase):
    def test_janela(self):
        a,b,anos=janela("2019-12-31","2019-12-31",2)
        self.assertEqual(list(anos),[2019,2020])
        self.assertEqual(str(b),"2020-01-02")
        self.assertEqual(list(janela("2020-12-31","2020-12-31",15)[2]),[2020])
    def test_agregacao(self):
        def ms(d): return int(datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp()*1000)
        e=agregar(2020,{f"42:{ms('2020-01-01')}":3,f"42:{ms('2020-01-03')}":2})[0]
        self.assertEqual((e["registros_na_aoi"],e["datas_distintas"],e["lacunas"]),(5,2,1))
        self.assertIsNone(e["registros_totais"])
    def test_cache(self):
        calls=[]
        def consulta(*args):
            calls.append(args)
            return []
        with tempfile.TemporaryDirectory() as p:
            args=(p,AOI,"teste v1","2020-01-01","2020-01-02")
            self.assertEqual(catalogo(*args,consulta=consulta)["origem"],"GEE")
            self.assertEqual(catalogo(*args,consulta=consulta)["origem"],"cache local")
            self.assertEqual(len(calls),1)
            catalogo(*args,atualizar=True,consulta=consulta)
            self.assertEqual(len(calls),2)
    def test_invalidos(self):
        with self.assertRaises(ValueError): janela("2021-01-01","2021-01-02",0)
        with self.assertRaises(ValueError): janela("2020-02-01","2020-01-01",0)
