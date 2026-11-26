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
    def test_margem_atraves_do_ano_e_limites_dataset(self):
        from burngeoflow.aquisicao.catalogo import janela
        inicio, fim, anos = janela("2019-12-31", "2020-01-01", 2)
        self.assertEqual(str(inicio), "2019-12-29")
        self.assertEqual(str(fim), "2020-01-03")
        self.assertEqual(list(anos), [2019, 2020])
        inicio, fim, anos = janela("2001-01-01", "2001-01-01", 30)
        self.assertEqual(str(inicio), "2001-01-01")
        self.assertEqual(list(anos), [2001])
        inicio, fim, anos = janela("2020-12-31", "2020-12-31", 30)
        self.assertEqual(str(fim), "2020-12-31")
        self.assertEqual(list(anos), [2020])

    def test_datas_invalidas_e_periodos_excessivos(self):
        for ini, fim, margem in [
            ("2020-02-30", "2020-03-10", 0),
            ("20200101", "2020-01-10", 0),
            ("2000-12-31", "2001-01-01", 0),
            ("2020-01-01", "2021-01-01", 0),
            ("2018-01-01", "2020-01-01", 0),
            ("2020-01-01", "2020-01-02", -1),
            ("2020-01-01", "2020-01-02", 366),
            ("2020-01-02", "2020-01-01", 0),
        ]:
            with self.subTest(inicio=ini, fim=fim, margem=margem):
                with self.assertRaises(ValueError):
                    janela(ini, fim, margem)

    def test_cache_identidade_e_integridade(self):
        import json
        from pathlib import Path
        from burngeoflow.aquisicao.catalogo import catalogo
        chamadas=[]
        def consulta(*args):
            chamadas.append(args)
            return [{"id": 101, "ano": 2020}]
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            params=(base, AOI, "fonte-testada", "2020-01-01", "2020-01-10")
            primeiro=catalogo(*params, consulta=consulta)
            self.assertEqual(primeiro["origem"], "GEE")
            segundo=catalogo(*params, consulta=consulta)
            self.assertEqual(segundo["origem"], "cache local")
            terceiro=catalogo(base, AOI, "versao-diferente", "2020-01-01",
                              "2020-01-10", consulta=consulta)
            self.assertEqual(terceiro["origem"], "GEE")
            self.assertEqual(len(chamadas), 2)
            arquivos=list(base.glob("*.json"))
            self.assertEqual(len(arquivos), 2)
            destino=next(p for p in arquivos if
                         json.loads(p.read_text())["origem_aoi"]=="fonte-testada")
            registro=json.loads(destino.read_text())
            registro["fonte"]="fonte-alterada"
            destino.write_text(json.dumps(registro))
            with self.assertRaisesRegex(ValueError, "corrompido"):
                catalogo(*params, consulta=consulta)
            self.assertEqual(len(chamadas), 2)
            catalogo(*params, consulta=consulta, atualizar=True)
            self.assertEqual(len(chamadas), 3)

    def test_invalidos(self):
        with self.assertRaises(ValueError): janela("2021-01-01","2021-01-02",0)
        with self.assertRaises(ValueError): janela("2020-02-01","2020-01-01",0)
