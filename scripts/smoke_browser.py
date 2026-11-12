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
            "dominancia_maior_patch_pct": "80",
            "indice_forma_medio_ponderado_area": "1.5",
        } for i, d in enumerate(DATAS)]
    elif caminho.endswith("/analysis"):
        nomes = ("centroide", "norte", "sul", "leste", "oeste")
        dados = {
            "disponivel": True,
            "pontos": [{
                "id_incendio": str(EVENTO), "data": d, "ponto": nome,
                "x_laea_m": str(1000 + i * 200 + j * 40),
                "y_laea_m": str(2000 + i * 100 + j * 70),
            } for i, d in enumerate(DATAS) for j, nome in enumerate(nomes)],
            "segmentos": [{
                "id_incendio": str(EVENTO),
                "data_anterior": DATAS[i-1], "data_atual": DATAS[i],
                "ponto": nome, "azimute_geodesico_graus": str(50+j*25),
                "distancia_geodesica_km": "1.5",
            } for i in range(1, len(DATAS)) for j, nome in enumerate(nomes)],
            "indicadores": [{
                "id_incendio": str(EVENTO),
                "data_anterior": DATAS[i-1], "data_atual": DATAS[i],
                "deslocamento_centroide_km": "1.5",
                "avanco_norte_km": "0.5", "avanco_sul_km": "0.1",
                "avanco_leste_km": "0.7", "avanco_oeste_km": "0.2",
                "delta_amplitude_ns_km": "0.4", "delta_amplitude_lo_km": "0.5",
                "indice_forma_atual": "1.7", "delta_indice_forma": "0.1",
                "perimetro_atual_km": "10.0", "jaccard_geometrico": "0.7",
            } for i in range(1, len(DATAS))],
        }
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
            assert page.locator(".sidebar").evaluate(
                "el => getComputedStyle(el).position"
            ) == "sticky", "A barra lateral precisa acompanhar a rolagem"
            page.get_by_role("tab", name="Paisagem").click()
            page.get_by_role("heading", name="Paisagem e componentes").wait_for()
            assert page.locator(".chart-panel").count() == 4
            page.get_by_role("tab", name="Expansão").click()
            page.get_by_role("heading", name="Expansão e incorporação geométrica").wait_for()
            page.evaluate("window.scrollTo(0, 530)")
            page.wait_for_timeout(100)
            lateral = page.locator(".sidebar").bounding_box()
            assert lateral is not None and abs(lateral["y"] - 76) < 4, (
                "Barra lateral não acompanhou a rolagem do desktop"
            )
            page.evaluate("window.scrollTo(0, 0)")
            page.get_by_role("tab", name="Movimento").click()
            page.get_by_role("heading", name="Cinco trajetórias representativas").wait_for()
            page.get_by_role("tab", name="Direções").click()
            page.get_by_role("heading", name="Direções e rosáceas").wait_for()
            assert page.locator(".rose-card").count() == 7
            page.get_by_role("tab", name="Forma").click()
            page.get_by_role("heading", name="Forma e deformação").wait_for()
            assert page.locator(".chart-panel").count() == 4
            assert not errors, f"Falhas JavaScript nas novas abas: {errors}"
            page.set_viewport_size({"width": 390, "height": 840})
            assert page.locator(".sidebar").evaluate(
                "el => getComputedStyle(el).position"
            ) == "fixed", "No mobile o menu deve continuar sendo um drawer"
            page.get_by_role("button", name="Abrir menu").click()
            assert "sidebar-open" in (page.locator(".sidebar").get_attribute("class") or "")
            page.locator(".global-header").get_by_role("button", name="Fechar menu").click()
            browser.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)
    print("[OK] Browser: página leve, mapa sob demanda e sem pageerror")


if __name__ == "__main__":
    testar()
