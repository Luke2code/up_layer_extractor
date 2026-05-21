from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


REPO_ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT = REPO_ROOT / "docs" / "kamenice-v4-ui-smoke.png"
UI_URL = os.environ.get("UP_LAYER_UI_URL", "http://127.0.0.1:4100")
KAMENICE_PDF = next(
    path
    for path in [
        Path("/mnt/c/Users/Me/Downloads/kamenice hlv.pdf"),
        Path("/mnt/c/Users/Me/Downloads/A_PV___KAMENICE___538299___UZ_9_15___HLV.pdf"),
        Path("/mnt/c/stg_db/data/up_import/A_PV/KAMENICE___538299/UZ_9_15/A_PV___KAMENICE___538299___UZ_9_15___HLV.pdf"),
    ]
    if path.exists()
)


def assert_no_browser_errors(console_errors: list[str], page_errors: list[str]) -> None:
    if console_errors:
        raise AssertionError("browser console errors: " + "; ".join(console_errors))
    if page_errors:
        raise AssertionError("browser page errors: " + "; ".join(page_errors))


def main() -> None:
    SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
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

        review_separator = page.get_by_test_id("resize-review")
        results_separator = page.get_by_test_id("resize-results")
        review_before = review_separator.bounding_box()
        results_before = results_separator.bounding_box()
        if not review_before or not results_before:
            raise AssertionError("layout separators are not measurable")
        if review_before["width"] > 3 or results_before["height"] > 3:
            raise AssertionError(f"layout separators are not simple 1px lines: review={review_before}, results={results_before}")
        page.mouse.move(review_before["x"] + 0.5, review_before["y"] + review_before["height"] / 2)
        page.mouse.down()
        page.mouse.move(review_before["x"] - 80, review_before["y"] + review_before["height"] / 2)
        page.mouse.up()
        review_after = review_separator.bounding_box()
        if not review_after or abs(review_after["x"] - review_before["x"]) < 20:
            raise AssertionError(f"review panel separator did not move after drag: before={review_before}, after={review_after}")

        with page.expect_response(lambda response: "/api/extract_upload" in response.url and response.status == 200, timeout=240_000):
            page.set_input_files('input[type="file"]', str(KAMENICE_PDF))
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Mode: merged_polygons").first).to_be_visible(timeout=30_000)
        expect(page.get_by_text("Features: 1265").first).to_be_visible(timeout=30_000)
        expect(page.get_by_text("Raw fragments: 56642").first).to_be_visible(timeout=30_000)

        expect(page.get_by_role("button", name="UP", exact=True)).to_be_visible()
        page.get_by_role("button", name="Legend", exact=True).click()
        legend_image = page.locator('img[alt="Legend crop"]')
        expect(legend_image).to_be_visible(timeout=30_000)
        if not legend_image.evaluate("(img) => img.complete && img.naturalWidth > 0 && img.naturalHeight > 0"):
            raise AssertionError("legend crop image did not load through the UI")

        page.get_by_test_id("legend-item-BU").click()
        expect(page.get_by_text("two_symbols_detected").first).to_be_visible(timeout=10_000)
        expect(page.get_by_text("stav_stabil").first).to_be_visible(timeout=10_000)
        expect(page.get_by_text("navrh").first).to_be_visible(timeout=10_000)
        expect(page.get_by_role("button", name="Vector Definitions")).to_be_visible(timeout=10_000)
        expect(page.get_by_text("BU").first).to_be_visible(timeout=10_000)
        expect(page.get_by_text("not checked / unreviewed / not eligible").first).to_be_visible(timeout=10_000)

        page.get_by_role("button", name="Toggle BU").click()
        expect(page.get_by_text("checked / unreviewed / not eligible").first).to_be_visible(timeout=10_000)
        page.get_by_role("button", name="Approve").click()
        expect(page.get_by_text("checked / approved / eligible").first).to_be_visible(timeout=10_000)

        page.get_by_test_id("legend-item-BH").click()
        expect(page.get_by_text("missing_expected_symbol_requires_review").first).to_be_visible(timeout=10_000)
        expect(page.get_by_text("missing requires review").first).to_be_visible(timeout=10_000)

        page.get_by_label("Manual legend crop bbox").fill("90,1180,710,2175")
        page.get_by_placeholder("note / reason").fill("v4 smoke manual crop trace")
        with page.expect_response(lambda response: "/api/manual/legend_crop" in response.url and response.status == 200, timeout=30_000):
            page.get_by_role("button", name="Save crop").click()
        expect(page.get_by_text("saved_for_review")).to_be_visible(timeout=10_000)

        page.screenshot(path=str(SCREENSHOT), full_page=True)
        browser.close()

    assert_no_browser_errors(console_errors, page_errors)
    print(f"kamenice v4 ui smoke passed; screenshot={SCREENSHOT}; pdf={KAMENICE_PDF}")


if __name__ == "__main__":
    main()
