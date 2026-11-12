"""Testes de visualização local, sem Streamlit e sem acesso ao GEE."""
from __future__ import annotations

import csv
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shapely.geometry import box, mapping

from burngeoflow.visualizacao.dados import (
    ErroVisualizador, assinatura_arquivos, camada_dia,
    carregar_evento, caminhos, descobrir_eventos, limites_dia,
    linha_dia, transicao_para,
)

EVENTO = 24340828


def criar_caso(base: Path, *, metrico: bool = True):
    arquivos = caminhos(base, EVENTO)
    arquivos["p1"].parent.mkdir(parents=True, exist_ok=True)
    datas = ["2020-09-10", "2020-09-11", "2020-09-12"]
    componentes = []
    rastreadas = []
    for indice, dia in enumerate(datas):
        for rank, geom in enumerate([
            box(-56.0, -17.0, -55.99 + indice / 1000, -16.99),
            box(-55.97, -17, -55.96, -16.99)
        ], 1):
            componentes.append({
                "type": "Feature", "properties": {
                    "data": dia, "id_incendio": EVENTO,
                    "rank": rank, "area_km2": float(rank),
                },
                "geometry": mapping(geom),
            })
            if rank == 1:
                rastreadas.append({
                    "type": "Feature", "properties": {
                        "data": dia, "id_incendio": EVENTO,
                        "rank_global": 1
                    },
                    "geometry": mapping(geom),
                })
    for nome, feicoes in (("p1", componentes), ("p2", rastreadas)):
        arquivos[nome].write_text(json.dumps({
            "type": "FeatureCollection", "features": feicoes,
        }), encoding="utf-8")
    if not metrico:
        return arquivos
    arquivos["serie"].parent.mkdir(parents=True, exist_ok=True)
    linhas = [
        {
            "data": d, "id_incendio": EVENTO, "numero_patches": 2,
            "area_total_laea_km2": 50+i,
            "p2_area_laea_km2": 40+i,
        }
        for i, d in enumerate(datas)
    ]
    with arquivos["serie"].open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    trans = [
        {"data_anterior": a, "data_atual": b, "dias_intervalo": 1,
         "id_incendio": EVENTO}
        for a, b in zip(datas, datas[1:])
    ]
    with arquivos["transicoes"].open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(trans[0]))
        w.writeheader()
        w.writerows(trans)
    arquivos["resumo5"].write_text(json.dumps({
        "id_incendio": EVENTO,
        "sha256_p1": sha256(arquivos["p1"].read_bytes()).hexdigest(),
        "sha256_p2": sha256(arquivos["p2"].read_bytes()).hexdigest(),
    }), encoding="utf-8")
    arquivos["resumo6"].parent.mkdir(parents=True, exist_ok=True)
    arquivos["resumo6"].write_text(json.dumps({
        "id_incendio": EVENTO,
        "status_cientifico": "revisao_geometrica_pendente",
        "validacao_externa_concluida": False,
    }), encoding="utf-8")
    return arquivos


class TesteLeituraVisualizador(unittest.TestCase):
    def test_interface_e_compilavel_sem_dependencias_opcionais(self):
        caminho = Path(__file__).resolve().parents[1] / "visualizador.py"
        codigo = caminho.read_text(encoding="utf-8")
        compile(codigo, str(caminho), "exec")

    def test_discovery_e_timeline(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            criar_caso(base)
            self.assertEqual(descobrir_eventos(base), [EVENTO])
            ev = carregar_evento(base, EVENTO)
            self.assertTrue(ev["completo"])
            self.assertEqual(len(ev["datas"]), 3)
            self.assertEqual(len(ev["p1_por_data"]["2020-09-11"]), 2)
            self.assertEqual(ev["p2_por_data"]["2020-09-11"]["properties"]
                             ["rank_global"], 1)
            self.assertEqual(linha_dia(ev, "2020-09-12")["numero_patches"], "2")
            self.assertEqual(
                transicao_para(ev, "2020-09-11")["data_anterior"],
                "2020-09-10",
            )
            self.assertIsNone(transicao_para(ev, "2020-09-10"))
            geo = camada_dia(ev, "2020-09-11")
            self.assertEqual(geo["type"], "FeatureCollection")
            self.assertEqual(len(geo["features"]), 3)
            so_p2 = camada_dia(ev, "2020-09-11",
                               incluir_p1=False)
            self.assertEqual(len(so_p2["features"]), 1)
            self.assertEqual(
                so_p2["features"][0]["properties"]["rank_global"], 1
            )
            minx, miny, maxx, maxy = limites_dia(
                ev["p1_por_data"]["2020-09-11"]
            )
            self.assertTrue(minx < maxx and miny < maxy)

    def test_geometrias_sem_metricas_sao_visiveis(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            criar_caso(base, metrico=False)
            ev = carregar_evento(base, EVENTO)
            self.assertFalse(ev["completo"])
            self.assertEqual(len(ev["datas"]), 3)
            self.assertEqual(ev["serie"], [])

    def test_cache_altera_quando_insumo_modificado(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            paths = criar_caso(base)
            s0 = assinatura_arquivos(paths)
            paths["p1"].write_text(paths["p1"].read_text() + " ", encoding="utf-8")
            self.assertNotEqual(s0, assinatura_arquivos(paths))

    def test_rejeita_geometria_de_outro_evento(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            paths = criar_caso(base, metrico=False)
            p2 = json.loads(paths["p2"].read_text(encoding="utf-8"))
            p2["features"][0]["properties"]["id_incendio"] = 100
            paths["p2"].write_text(json.dumps(p2), encoding="utf-8")
            with self.assertRaisesRegex(ErroVisualizador, "ID/data"):
                carregar_evento(base, EVENTO)

    def test_nao_exibe_metricas_de_outros_geojsons(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            paths = criar_caso(base)
            paths["p1"].write_text(
                paths["p1"].read_text(encoding="utf-8") + " ",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ErroVisualizador, "alterada"):
                carregar_evento(base, EVENTO)

    def test_csv_datas_diferentes_bloqueiam(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            paths = criar_caso(base)
            texto = paths["serie"].read_text(encoding="utf-8")
            paths["serie"].write_text(
                texto.replace("2020-09-11", "2020-09-14"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ErroVisualizador, "datas P1/P2"):
                carregar_evento(base, EVENTO)

    def test_sem_par_de_geojson_nao_aparece(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            paths = criar_caso(base)
            paths["p2"].unlink()
            self.assertEqual(descobrir_eventos(base), [])
            with self.assertRaisesRegex(ErroVisualizador, "não possui P1/P2"):
                carregar_evento(base, EVENTO)

    def test_data_inexistente(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            criar_caso(base)
            ev = carregar_evento(base, EVENTO)
            with self.assertRaisesRegex(ErroVisualizador, "Data ausente"):
                camada_dia(ev, "2030-01-01")


if __name__ == "__main__":
    unittest.main()
