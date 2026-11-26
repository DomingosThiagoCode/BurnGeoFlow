"""Regressão offline da malha IBGE de estados e Brasil; nenhuma rede."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile
import json
import unittest

import shapefile
from pyproj import CRS
from shapely.geometry import shape

from burngeoflow.aquisicao.limites_ibge import (
    UFS, resolver_uf_ou_brasil,
)


class TestLimitesIBGE(unittest.TestCase):
    @staticmethod
    def escrever_malha(pasta: Path) -> None:
        nome = pasta / "BR_UF_2024"
        with shapefile.Writer(str(nome), shapeType=shapefile.POLYGON) as w:
            w.field("SIGLA_UF", "C", size=2)
            w.field("CD_UF", "C", size=2)
            w.field("NM_UF", "C", size=40)
            w.poly([[[-44, -23], [-44, -22], [-43, -22], [-43, -23], [-44, -23]]])
            w.record("RJ", "33", "Rio de Janeiro")
            w.poly([[[-56, -20], [-56, -19], [-55, -19], [-55, -20], [-56, -20]]])
            w.record("MS", "50", "Mato Grosso do Sul")
        nome.with_suffix(".prj").write_text(
            CRS.from_epsg(4674).to_wkt(), encoding="utf-8"
        )
        with ZipFile(pasta / "BR_UF_2024.zip", "w") as z:
            for ext in (".shp", ".shx", ".dbf", ".prj"):
                z.write(nome.with_suffix(ext), "BR_UF_2024" + ext)

    def test_estado_pais_e_cache_local(self):
        with TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            self.escrever_malha(pasta)
            with patch(
                "burngeoflow.aquisicao.limites_ibge.urlopen",
                side_effect=AssertionError("rede não deveria ser acessada"),
            ):
                rj = resolver_uf_ou_brasil("UF:RJ", pasta)
                ms = resolver_uf_ou_brasil("UF:MS", pasta)
                br = resolver_uf_ou_brasil("Brasil", pasta)
                rj_cache = resolver_uf_ou_brasil("UF:RJ", pasta)
            self.assertEqual(rj["origem"], rj_cache["origem"])
            self.assertTrue(shape(rj["geometria"]).equals(
                shape(rj_cache["geometria"])
            ))
            self.assertIn("IBGE Malha Territorial 2024", rj["origem"])
            self.assertAlmostEqual(shape(rj["geometria"]).area, 1, places=4)
            self.assertAlmostEqual(shape(ms["geometria"]).area, 1, places=4)
            self.assertAlmostEqual(shape(br["geometria"]).area, 2, places=4)
            self.assertEqual(len(UFS), 27)
            self.assertEqual(len(list(pasta.glob("malha_ibge_2024_*.json"))), 3)

    def test_invalidos_nao_baixam(self):
        with TemporaryDirectory() as tmp:
            for valor in ("UF:XX", "UF:../../", "Amazon", "", "RJ"):
                with self.assertRaises(ValueError):
                    resolver_uf_ou_brasil(valor, Path(tmp))
            self.assertFalse(list(Path(tmp).iterdir()))

    def test_zip_com_camadas_imprevistas_falha_sem_extrair(self):
        with TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            with ZipFile(pasta / "BR_UF_2024.zip", "w") as z:
                z.writestr("../../fora.txt", "perigoso")
            with self.assertRaisesRegex(ValueError, "camada BR_UF_2024"):
                resolver_uf_ou_brasil("UF:RJ", pasta)
            self.assertFalse((pasta / "fora.txt").exists())


if __name__ == "__main__":
    unittest.main()
