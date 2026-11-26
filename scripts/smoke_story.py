"""Smoke test da landing /apresentacao/ com dados históricos versionados.

Rodar após npm run build e instalar Playwright/Chromium:
    python scripts/smoke_story.py
Não chama Google Earth Engine e não modifica dados científicos.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"


def testar() -> None:
    assert (DIST / "apresentacao" / "index.html").is_file(), (
        "A entrada multipagina da landing não foi compilada"
    )
    handler = partial(SimpleHTTPRequestHandler, directory=str(DIST))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{server.server_port}/apresentacao/",
                      wait_until="networkidle", timeout=30000)
            page.get_by_role("heading", name="O território não permanece imóvel.").wait_for()
            page.locator(".story-map-loading").wait_for(state="hidden", timeout=30000)
            assert page.locator(".story-steps .story-step").count() == 8
            assert page.get_by_text("Áreas queimadas mapeadas.", exact=False).count() >= 1
            assert page.locator(".story-visual").evaluate(
                "e => getComputedStyle(e).position"
            ) == "sticky"
            pasta = ROOT / "artifacts" / "story"
            pasta.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(pasta / "01-hero-desktop.png"))
            page.evaluate("""() => {
              const el = document.querySelectorAll('.story-step')[2];
              window.scrollTo(0, scrollY + el.getBoundingClientRect().top + innerHeight * .6);
            }""")
            page.wait_for_timeout(200)
            assert "scene-2" in (page.locator(".story-visual").get_attribute("class") or "")
            assert page.locator("path.story-p1").get_attribute("d")
            page.evaluate("""() => {
              const el = document.querySelectorAll('.story-step')[5];
              window.scrollTo(0, scrollY + el.getBoundingClientRect().top + innerHeight * .7);
            }""")
            page.wait_for_timeout(250)
            assert "scene-5" in (page.locator(".story-visual").get_attribute("class") or "")
            assert page.locator(".story-visual svg g path").count() == 5
            page.screenshot(path=str(pasta / "02-trajetorias-desktop.png"))
            page.evaluate("""() => {
              const el = document.querySelectorAll('.story-step')[6];
              window.scrollTo(0, scrollY + el.getBoundingClientRect().top + innerHeight * .5);
            }""")
            page.wait_for_timeout(250)
            assert "scene-6" in (page.locator(".story-visual").get_attribute("class") or "")
            assert page.locator("path.story-igt").get_attribute("d")
            assert page.get_by_role("link", name="Explorar o BurnGeoFlow").get_attribute("href") == "/"
            assert not errors, f"Erros JavaScript: {errors}"
            page.set_viewport_size({"width": 390, "height": 844})
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(250)
            assert page.locator(".story-visual").evaluate(
                "e => getComputedStyle(e).position"
            ) == "sticky"
            assert page.locator(".story-visual").bounding_box()["height"] > 250
            page.screenshot(path=str(pasta / "03-mobile.png"))
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    print("[OK] Landing: 8 cenas, SVG real, TR/IGT, desktop e mobile")


if __name__ == "__main__":
    testar()
