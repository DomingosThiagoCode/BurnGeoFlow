import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from unittest.mock import patch

import shapefile
from pyproj import CRS
from backend.app.api.catalogo import BIOMAS, resolver_regiao

class TestCatalogoRegiao(unittest.TestCase):
    def test_zip_local_e_cache(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            with shapefile.Writer(str(base / "biomas"), shapeType=shapefile.POLYGON) as w:
                w.field("BIOMA", "C", size=40)
                for i, nome in enumerate(sorted(BIOMAS)):
                    x = -60 + i
                    w.poly([[[x,-20],[x,-19],[x+0.5,-19],[x+0.5,-20],[x,-20]]])
                    w.record(nome)
            (base / "biomas.prj").write_text(CRS.from_epsg(4674).to_wkt(), encoding="utf-8")
            with ZipFile(base / "Biomas_250mil.zip", "w") as z:
                for ext in ("shp","shx","dbf","prj"):
                    z.write(base / ("biomas."+ext), "pasta/biomas."+ext)
            dados = resolver_regiao("Pantanal", base)
            self.assertEqual(dados["geometria"]["type"], "Polygon")
            self.assertIn("IBGE Biomas 2019", dados["origem"])
            with patch("backend.app.api.catalogo.urlopen", side_effect=AssertionError("cache não usado")):
                self.assertEqual(resolver_regiao("Pantanal", base)["origem"], dados["origem"])

    def test_erro_de_fonte_distinto_do_gee(self):
        from urllib.error import HTTPError
        with TemporaryDirectory() as tmp, patch("backend.app.api.catalogo.urlopen",
                side_effect=HTTPError("https://example.test",403,"Forbidden",None,None)):
            with self.assertRaisesRegex(RuntimeError, "antes da consulta GEE"):
                resolver_regiao("Pantanal", Path(tmp))
