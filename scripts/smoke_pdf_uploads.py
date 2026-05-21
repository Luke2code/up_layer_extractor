from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


REPO_ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = REPO_ROOT / "docs" / "ui_upload_smokes"
UI_URL = os.environ.get("UP_LAYER_UI_URL", "http://127.0.0.1:4100")
CASES = [
    {
        "name": "bykev-hlv",
        "path": Path("/mnt/c/Users/Me/Downloads/bykev_3-hlavní výkres.pdf"),
        "mode": "raw_polygons",
        "features": 4832,
    },
    {
        "name": "ricany-hlv",
        "path": Path("/mnt/c/demo/Input/UP_538728_RICANY_HLV.pdf"),
        "mode": "raw_polygons",
        "features": 49967,
    },
    {
        "name": "kamenice-hlv",
        "path": next(
            path
            for path in [
                Path("/mnt/c/Users/Me/Downloads/kamenice hlv.pdf"),
                Path("/mnt/c/Users/Me/Downloads/A_PV___KAMENICE___538299___UZ_9_15___HLV.pdf"),
                Path("/mnt/c/stg_db/data/up_import/A_PV/KAMENICE___538299/UZ_9_15/A_PV___KAMENICE___538299___UZ_9_15___HLV.pdf"),
            ]
            if path.exists()
        ),
        "mode": "merged_polygons",
        "features": 1265,
        "raw_fragments": 56642,
    },
]


def main() -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    page_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1050})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.goto(UI_URL, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("UP Layer Extractor")).to_be_visible(timeout=15_000)

        for case in CASES:
            path = case["path"]
            if not path.exists():
                raise AssertionError(f"missing smoke PDF: {path}")
            with page.expect_response(lambda response: "/api/extract_upload" in response.url and response.status == 200, timeout=180_000):
                page.set_input_files('input[type="file"]', str(path))
            page.wait_for_load_state("networkidle")
            expect(page.get_by_text(f"Mode: {case['mode']}").first).to_be_visible(timeout=30_000)
            expect(page.get_by_text(f"Features: {case['features']}").first).to_be_visible(timeout=30_000)
            if "raw_fragments" in case:
                expect(page.get_by_text(f"Raw fragments: {case['raw_fragments']}").first).to_be_visible(timeout=30_000)
                page.get_by_role("button", name="Legend Rows").click()
                expect(page.get_by_text("BX.c").first).to_be_visible(timeout=10_000)
                page.get_by_role("button", name="Pipeline").click()
                expect(page.get_by_text("tessellated_fill_merge").first).to_be_visible(timeout=10_000)
                expect(page.get_by_text("raw_fragment_false_success_gate_v1").first).to_be_visible(timeout=10_000)
            page.screenshot(path=str(SCREENSHOT_DIR / f"{case['name']}.png"), full_page=True)

        browser.close()

    if console_errors:
        raise AssertionError("browser console errors: " + "; ".join(console_errors))
    if page_errors:
        raise AssertionError("browser page errors: " + "; ".join(page_errors))
    print(f"pdf upload smokes passed; screenshots={SCREENSHOT_DIR}")


if __name__ == "__main__":
    main()
