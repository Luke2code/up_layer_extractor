from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_URL = os.environ.get("UP_LAYER_UI_URL", "http://127.0.0.1:4100")
SCREENSHOT = REPO_ROOT / "docs" / "kvetnice-v7-legend-unavailable-reason.png"


def main() -> None:
    SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    page_errors: list[str] = []
    request_urls: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1320, "height": 900})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on("request", lambda request: request_urls.append(request.url))
        page.goto(UI_URL, wait_until="networkidle")
        expect(page.get_by_text("UP Layer Extractor")).to_be_visible(timeout=15_000)
        expect(page.get_by_text("Plan source: embedded_raster").first).to_be_visible(timeout=10_000)
        page.get_by_role("button", name="Legend", exact=True).click()
        expect(page.get_by_test_id("legend-unavailable")).to_be_visible(timeout=10_000)
        expect(page.get_by_text("GeoJSON-only").first).to_be_visible(timeout=10_000)
        if page.get_by_role("button", name="Crop 1").count() or page.get_by_role("button", name="Crop 2").count():
            raise AssertionError("empty crop buttons are shown for the GeoJSON-only sample")
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        browser.close()
    if console_errors:
        raise AssertionError("browser console errors: " + "; ".join(console_errors))
    if page_errors:
        raise AssertionError("browser page errors: " + "; ".join(page_errors))
    direct_8787 = [url for url in request_urls if "127.0.0.1:8787" in url or "localhost:8787" in url]
    if direct_8787:
        raise AssertionError("browser made direct 8787 requests: " + "; ".join(direct_8787[:5]))
    print("kvetnice v7 legend sample smoke passed")
    print(f"screenshot={SCREENSHOT}")


if __name__ == "__main__":
    main()
