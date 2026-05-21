from __future__ import annotations

import re
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


REPO_ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT = REPO_ROOT / "docs" / "webapp-smoke.png"
UI_URL = os.environ.get("UP_LAYER_UI_URL", "http://127.0.0.1:4100")


def main() -> None:
    console_errors: list[str] = []
    page_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.goto(UI_URL, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        expect(page.get_by_text("UP Layer Extractor")).to_be_visible(timeout=15_000)
        expect(page.get_by_text("112 / 112 features")).to_be_visible(timeout=10_000)
        expect(page.get_by_text("RZVP.BI").first).to_be_visible()

        page.get_by_role("button", name="Edit border").click()
        expect(page.get_by_text("editing")).to_be_visible()
        page.get_by_role("button", name="Add vertex").click()
        expect(page.get_by_text("Vertices:")).to_be_visible()
        page.get_by_role("button", name="Cancel").click()

        page.get_by_role("button", name="ZMEN").click()
        expect(page.get_by_text("19 / 112 features")).to_be_visible()
        page.get_by_role("button", name="Text Definitions").click()
        expect(page.get_by_role("cell", name=re.compile(r"^Z12$")).first).to_be_visible()
        page.get_by_role("button", name="Classification").click()
        expect(page.get_by_text("existing_class_target_scope_match").first).to_be_visible()
        page.get_by_role("button", name="Remapping").click()
        expect(page.get_by_text("ZMEN.Z").first).to_be_visible()

        page.screenshot(path=str(SCREENSHOT), full_page=True)
        browser.close()

    if console_errors:
        raise AssertionError("browser console errors: " + "; ".join(console_errors))
    if page_errors:
        raise AssertionError("browser page errors: " + "; ".join(page_errors))
    print(f"webapp smoke passed; screenshot={SCREENSHOT}")


if __name__ == "__main__":
    main()
