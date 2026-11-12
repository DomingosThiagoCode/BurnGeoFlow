"""Browser smoke test do React compilado com API simulada e sem GEE.

Instalar somente no CI ou no ambiente de QA:
    pip install playwright
    python -m playwright install chromium
    python scripts/smoke_browser.py

O teste reproduz o carregamento e um clique de mapa em Chromium real.
Não usa GeoJSONs privados e não faz uma validação de desempenho no Windows.
"""
from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"
EVENTO = 24340828
DATAS = ["2020-09-10", "2020-09-11", "2020-09-12"]


def resumo():
    return {
        "id_incendio": EVENTO,
        "datas": DATAS,
        "periodo_inicio": DATAS[0],
        "periodo_fim": DATAS[-1],
        "total_datas": 3,
        "tem_series": True,
        "tem_transicoes": True,
        "status_cientifico": "revisao_geometrica_pendente",
        "validacao_externa_concluida": False,
        "dias_sobreposicao_p1_pendentes": [],
        "observacao": "Dados sintéticos para teste de browser.",
    }


def camada(dia, layer):
    x = -56 + DATAS.index(dia) * .01
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {
                "data": dia, "rank": 1, "rank_global": 1,
                "id_incendio": EVENTO, "area_km2": 1.2,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [x, -17], [x+.02, -17],
                    [x+.02, -16.98], [x, -16.98], [x, -17],
                ]],
            },
        }],
    }


def responder_api(route):
    uri = urlparse(route.request.url)
    caminho = uri.path
    if caminho == "/api/events":
        dados = [{"id_incendio": EVENTO}]
    elif caminho == "/api/jobs":
        dados = []
    elif caminho.endswith("/overview"):
        dados = resumo()
    elif caminho.endswith("/series"):
        dados = [{
            "id_incendio": str(EVENTO), "data": d,
            "area_total_laea_km2": str(i + 10),
            "p2_area_laea_km2": str(i + 8),
            "numero_patches": "1",
            "dominancia_cobertura_p2_pct": "80",
        } for i, d in enumerate(DATAS)]
    elif caminho.endswith("/transitions"):
        dados = [{
            "id_incendio": str(EVENTO),
            "data_anterior": DATAS[i-1],
            "data_atual": DATAS[i],
            "dias_intervalo": "1",
            "area_nova_evento_km2": "1",
            "p2_incremento_ja_queimado_km2": "0.5",
            "eventos_convergencia": "1",
        } for i in range(1, len(DATAS))]
    elif caminho.endswith("/geometry"):
        dia = caminho.split("/")[-2]
        layer = "p2" if "layer=p2" in uri.query else "p1"
        dados = camada(dia, layer)
    elif caminho.endswith("/logs"):
        dados = {"job_id": "0" * 32, "lines": [], "truncated": False}
    else:
        route.fulfill(status=404, content_type="application/json", body="{}")
        return
    route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(dados),
    )


def testar() -> None:
    if not (DIST / "index.html").is_file():
        raise RuntimeError("Execute npm run build antes do smoke test")
    handler = partial(SimpleHTTPRequestHandler, directory=str(DIST))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--use-gl=angle",
                      "--use-angle=swiftshader"],
            )
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            assets = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.on("request", lambda req: assets.append(req.url))
            page.route("**/api/**", responder_api)
            base = "http://127.0.0.1:" + str(httpd.server_port)
            page.goto(base, wait_until="networkidle", timeout=30000)
            page.get_by_role("heading", name="Visão geral do incêndio").wait_for()
            page.get_by_role(
                "button", name="Abrir mapa do evento",
            ).wait_for()
            assert "Evento " + str(EVENTO) in page.locator("main").inner_text()
            assert not any("/geometry?" in url for url in assets), (
                "Página inicial acessou geometrias desnecessariamente"
            )
            assert not any("MapPanel-" in url for url in assets), (
                "Mapa foi carregado antes da ação do usuário"
            )
            assert not errors, f"Falhas JavaScript na página inicial: {errors}"
            page.get_by_role(
                "button", name="Abrir mapa do evento",
            ).click()
            page.locator(".maplibregl-canvas").wait_for(timeout=30000)
            page.wait_for_function(
                "() => document.querySelector('.maplibregl-canvas') !== null",
                timeout=30000,
            )
            page.wait_for_timeout(1000)
            assert any("/geometry?" in url for url in assets), (
                "Mapa não solicitou a geometria após ativação"
            )
            assert any("MapPanel-" in url for url in assets), (
                "Código cartográfico não foi carregado sob demanda"
            )
            assert not errors, f"Falhas JavaScript após abrir mapa: {errors}"
            page.get_by_role(
                "button", name="Fechar mapa e liberar memória",
            ).click()
            page.get_by_role(
                "button", name="Abrir mapa do evento",
            ).wait_for()
            browser.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)
    print("[OK] Browser: página leve, mapa sob demanda e sem pageerror")


if __name__ == "__main__":
    testar()
