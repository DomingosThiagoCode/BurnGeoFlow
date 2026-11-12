"""Etapa 5: reaproveita reparos auditados em TR/IGT sem editar P1/P2."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shapely.geometry import Polygon, mapping

from burngeoflow.analises.integracao import (
    ler_geometrias, conferir_auditoria_previa,
)

ID = 24340828
BOWTIE = Polygon([
    (-56.0, -17.0), (-55.999, -16.999), (-56.0, -16.999),
    (-55.999, -17.0), (-56.0, -17.0),
])


def arquivos(raiz: Path):
    pasta = raiz / "dados" / f"estudo_caso_{ID}"
    pasta.mkdir(parents=True)
    p1, p2 = [], []
    for indice, dia in enumerate(["2020-08-09", "2020-08-10"]):
        props = {
            "id_incendio": ID, "data": dia, "rank": 1,
            "rank_global": 1, "numero_componentes": 1,
            "area_km2": 0.005892, "area_total_km2": 0.005892,
        }
        p1.append({"type": "Feature", "properties": dict(props),
                   "geometry": mapping(BOWTIE)})
        p2.append({"type": "Feature", "properties": dict(props),
                   "geometry": mapping(BOWTIE)})
    pa = pasta / f"P1_componentes_{ID}.geojson"
    pb = pasta / f"P2_regiao_movel_{ID}.geojson"
    pa.write_text(json.dumps({"type": "FeatureCollection",
                              "features": p1}), encoding="utf-8")
    pb.write_text(json.dumps({"type": "FeatureCollection",
                              "features": p2}), encoding="utf-8")
    return pa, pb


def resumos(raiz: Path, p1: Path, p2: Path, audit: dict):
    e4 = raiz / "resultados" / "etapa4"
    e4.mkdir(parents=True)
    hashes = {k: sha256(p.read_bytes()).hexdigest()
              for k,p in (("p1",p1),("p2",p2))}
    p2reparados = audit["reparos_p2"]
    n1 = audit["geometrias_p1_reparadas_apos_projecao"]
    n2 = audit["numero_reparos_p2_para_comparacao"]
    for nome, arquivo in (
        ("tr", f"resumo_regiao_movel_{ID}.json"),
        ("igt", f"resumo_incrementos_{ID}.json"),
        ("consolidado", f"resumo_consolidado_tr_igt_{ID}.json"),
    ):
        origem = {
            "numero_reparos_p2_para_comparacao": n2,
            "reparos_p2_para_comparacao": p2reparados,
            ("geometrias_reparadas_apos_projecao" if nome == "tr"
             else "geometrias_p1_reparadas_apos_projecao"): n1,
        }
        if nome == "consolidado":
            data = {
                "auditoria_geometrica_consolidacao": origem,
                "hash_sha256_p1": hashes["p1"],
                "hash_sha256_p2": hashes["p2"],
            }
        else:
            data = {**origem, "sha256_p1": hashes["p1"],
                    "sha256_p2": hashes["p2"]}
        (e4 / arquivo).write_text(json.dumps(data), encoding="utf-8")


class TestesEtapa5Auditada(unittest.TestCase):
    def test_p1_e_p2_invalidos_reconciliados_sem_mudar_origem(self):
        with TemporaryDirectory() as temp:
            raiz = Path(temp)
            p1, p2 = arquivos(raiz)
            hashes = (sha256(p1.read_bytes()).hexdigest(),
                      sha256(p2.read_bytes()).hexdigest())
            audit = {}
            totais, selecionados, grupos, _ = ler_geometrias(
                p1, p2, ID, diagnostico=audit)
            )
            self.assertEqual(len(totais), 2)
            self.assertTrue(all(x.is_valid and x.area > 0
                                for x in selecionados.values()))
            self.assertEqual(len(grupos), 2)
            self.assertEqual(audit["geometrias_p1_reparadas_apos_projecao"], 2)
            self.assertEqual(audit["numero_reparos_p2_para_comparacao"], 2)
            self.assertEqual(
                hashes, (sha256(p1.read_bytes()).hexdigest(),
                         sha256(p2.read_bytes()).hexdigest()),
            )

    def test_confere_hashes_contagens_e_datas_de_etapa4(self):
        with TemporaryDirectory() as temp:
            raiz = Path(temp)
            p1, p2 = arquivos(raiz)
            audit = {}
            ler_geometrias(p1, p2, ID, diagnostico=audit)
            resumos(raiz, p1, p2, audit)
            conferir_auditoria_previa(raiz, ID, p1, p2, audit)
            self.assertEqual(
                audit["auditoria_etapa4_conferida"],
                "hashes_contagens_e_ranks",
            )

    def test_rejeita_relatorio_ausente_sem_apagar_brutos(self):
        with TemporaryDirectory() as temp:
            raiz = Path(temp)
            p1, p2 = arquivos(raiz)
            audit = {}
            ler_geometrias(p1, p2, ID, diagnostico=audit)
            with self.assertRaisesRegex(ValueError, "relatorio da Etapa 4 ausente"):
                conferir_auditoria_previa(raiz, ID, p1, p2, audit)
            self.assertTrue(p1.exists() and p2.exists())

    def test_rejeita_hash_divergente(self):
        with TemporaryDirectory() as temp:
            raiz = Path(temp)
            p1, p2 = arquivos(raiz)
            audit = {}
            ler_geometrias(p1, p2, ID, diagnostico=audit)
            resumos(raiz, p1, p2, audit)
            path = raiz / "resultados" / "etapa4" / f"resumo_incrementos_{ID}.json"
            dados = json.loads(path.read_text(encoding="utf-8"))
            dados["sha256_p2"] = "bad"
            path.write_text(json.dumps(dados), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash de p2 diverge"):
                conferir_auditoria_previa(raiz, ID, p1, p2, audit)

    def test_rejeita_mudanca_na_identidade_dos_reparos(self):
        with TemporaryDirectory() as temp:
            raiz = Path(temp)
            p1, p2 = arquivos(raiz)
            audit = {}
            ler_geometrias(p1, p2, ID, diagnostico=audit)
            resumos(raiz, p1, p2, audit)
            path = raiz / "resultados" / "etapa4" / f"resumo_regiao_movel_{ID}.json"
            dados = json.loads(path.read_text(encoding="utf-8"))
            dados["reparos_p2_para_comparacao"][0]["rank"] = 7
            path.write_text(json.dumps(dados), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "datas/ranks"):
                conferir_auditoria_previa(raiz, ID, p1, p2, audit)


if __name__ == "__main__":
    unittest.main()