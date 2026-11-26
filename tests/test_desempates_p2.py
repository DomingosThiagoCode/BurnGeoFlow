"""Evidência dos critérios D-004 com áreas exatas em coordenadas planas."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from shapely.geometry import box, mapping

from burngeoflow.processamento import metodologia_v2


ANTERIOR = "2020-09-10"
POSTERIOR = "2020-09-12"


class TestDesempatesP2(unittest.TestCase):
    def reconstruir(self, candidatos, posterior, *, bloqueado=False):
        # Isola a decisão de projeção e usa valores exatamente representáveis.
        componentes = {
            dia: [
                {"geometria": geo, "area_m2": geo.area, "ranks_origem": [rank]}
                for rank, geo in enumerate(geometrias, start=1)
            ]
            for dia, geometrias in ((ANTERIOR, candidatos), (POSTERIOR, [posterior]))
        }
        with TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            p1 = raiz / "p1.geojson"
            feicao = {
                "type": "Feature",
                "properties": {"data": ANTERIOR, "rank": 1, "id_incendio": 99},
                "geometry": mapping(box(0, 0, 1, 1)),
            }
            p1.write_text(
                json.dumps({"type": "FeatureCollection", "features": [feicao]}),
                encoding="utf-8",
            )
            pasta_saidas = raiz / metodologia_v2.VERSAO
            with patch.object(
                metodologia_v2, "_preparar_componentes", return_value=componentes
            ):
                if bloqueado:
                    with self.assertRaisesRegex(metodologia_v2.ErroMetodologia, "empate integral"):
                        metodologia_v2.reconstruir(p1, raiz)
                    self.assertFalse((pasta_saidas / "manifesto_metodologia.json").exists())
                    relatorio = json.loads(
                        (pasta_saidas / "diagnostico_bloqueio.json").read_text(encoding="utf-8")
                    )
                    return relatorio["detalhes"]["desempates_p2"]
                metodologia_v2.reconstruir(p1, raiz)
                manifesto = json.loads(
                    (pasta_saidas / "manifesto_metodologia.json").read_text(encoding="utf-8")
                )
                return manifesto["desempates_p2"]

    def test_registra_area_total_e_exclui_intersecoes_menores(self):
        evento, = self.reconstruir(
            [box(-1, 0, 1, 2), box(2, 0, 3, 2), box(1, 0, 2, 1)],
            box(0, 0, 4, 2),
        )
        self.assertEqual((evento["data"], evento["data_posterior"]), (ANTERIOR, POSTERIOR))
        self.assertEqual(evento["criterio"], "maior_area_total")
        self.assertEqual(evento["rank_escolhido"], 1)
        candidatos = evento["candidatos"]
        self.assertEqual([c["rank"] for c in candidatos], [1, 2])
        self.assertEqual([c["intersecao_m2"] for c in candidatos], [2, 2])
        self.assertEqual([c["area_total_m2"] for c in candidatos], [4, 2])
        self.assertEqual([c["distancia_centroides_m"] for c in candidatos], [2, 0.5])

    def test_registra_distancia_com_areas_empatadas(self):
        evento, = self.reconstruir(
            [box(0, 0, 1, 2), box(2, 0, 3, 2)],
            box(0, 0, 4, 2),
        )
        self.assertEqual(evento["criterio"], "menor_distancia_centroides")
        self.assertEqual(evento["rank_escolhido"], 2)

    def test_empate_integral_bloqueia_e_preserva_metricas(self):
        evento, = self.reconstruir(
            [box(0, 0, 1, 2), box(3, 0, 4, 2)],
            box(0, 0, 4, 2),
            bloqueado=True,
        )
        self.assertEqual(evento["criterio"], "empate_integral")
        self.assertIsNone(evento["rank_escolhido"])
        self.assertEqual(evento["candidatos"], [
            {"rank": 1, "intersecao_m2": 2, "area_total_m2": 2, "distancia_centroides_m": 1.5},
            {"rank": 2, "intersecao_m2": 2, "area_total_m2": 2, "distancia_centroides_m": 1.5},
        ])

    def test_sem_empate_nao_registra_desempate(self):
        self.assertEqual(
            self.reconstruir([box(0, 0, 1, 1), box(2, 0, 3, 2)], box(0, 0, 4, 2)),
            [],
        )
