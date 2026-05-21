from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright


REPO_ROOT = Path(__file__).resolve().parents[1]
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

SCREENSHOTS = {
    "source_colors": REPO_ROOT / "docs" / "kamenice-v8_1-plan-source-colors.png",
    "plan_on": REPO_ROOT / "docs" / "kamenice-v8_1-plan-snapshot-on.png",
    "artifact_fid329": REPO_ROOT / "docs" / "kamenice-v8_1-artifact-debug-fid329.png",
    "legend_default": REPO_ROOT / "docs" / "kamenice-v8_1-legend-fit-page-default.png",
    "legend_label": REPO_ROOT / "docs" / "kamenice-v8_1-legend-label-cleaned.png",
    "legend_focused": REPO_ROOT / "docs" / "kamenice-v8_1-legend-focused-vector-defs.png",
    "manual_crop": REPO_ROOT / "docs" / "kamenice-v8_1-manual-legend-crop.png",
    "up_zoom_steps": REPO_ROOT / "docs" / "kamenice-v8_2-up-zoom-steps-selected-label.png",
    "legend_compact": REPO_ROOT / "docs" / "kamenice-v8_2-legend-compact-candidate-status.png",
    "extraction_tab": REPO_ROOT / "docs" / "kamenice-v8_2-extraction-method-profile.png",
}


def assert_no_browser_errors(console_errors: list[str], page_errors: list[str], request_urls: list[str]) -> None:
    ignored_console_fragments = [
        "ResizeObserver loop completed",
    ]
    serious_console_errors = [
        message
        for message in console_errors
        if not any(fragment in message for fragment in ignored_console_fragments)
    ]
    if serious_console_errors:
        raise AssertionError("browser console errors: " + "; ".join(serious_console_errors))
    if page_errors:
        raise AssertionError("browser page errors: " + "; ".join(page_errors))
    direct_8787 = [url for url in request_urls if "127.0.0.1:8787" in url or "localhost:8787" in url]
    if direct_8787:
        raise AssertionError("browser made direct 8787 requests: " + "; ".join(direct_8787[:5]))


def upload_kamenice(page: Page) -> None:
    status = page.get_by_test_id("backend-status")
    with page.expect_response(lambda response: "/api/extract_upload" in response.url and response.status == 200, timeout=240_000):
        page.set_input_files('input[type="file"]', str(KAMENICE_PDF))
        expect(status).to_have_text("running", timeout=10_000)
    page.wait_for_load_state("networkidle")
    expect(status).to_have_text("completed", timeout=30_000)


def drag_manual_crop(page: Page) -> None:
    page.get_by_test_id("manual-crop-action").click()
    image_box = page.locator('img[alt="Legend crop"]').bounding_box()
    if not image_box:
        raise AssertionError("legend image has no bounding box")
    page.mouse.move(image_box["x"] + image_box["width"] * 0.12, image_box["y"] + image_box["height"] * 0.12)
    page.mouse.down()
    page.mouse.move(image_box["x"] + image_box["width"] * 0.72, image_box["y"] + image_box["height"] * 0.70)
    page.mouse.up()
    expect(page.get_by_test_id("manual-crop-rectangle")).to_be_visible(timeout=10_000)
    page.get_by_label("Manual legend crop bbox").scroll_into_view_if_needed()
    bbox_value = page.get_by_label("Manual legend crop bbox").input_value()
    if len([part for part in bbox_value.split(",") if part.strip()]) != 4:
        raise AssertionError(f"manual crop bbox was not updated: {bbox_value!r}")
    with page.expect_response(lambda response: "/api/manual/legend_crop" in response.url and response.status == 200, timeout=30_000):
        page.get_by_role("button", name="Save crop").click()
    expect(page.get_by_text("saved_for_review")).to_be_visible(timeout=10_000)


def main() -> None:
    for path in SCREENSHOTS.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    page_errors: list[str] = []
    request_urls: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1540, "height": 1100})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on("request", lambda request: request_urls.append(request.url))
        page.goto(UI_URL, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("UP Layer Extractor")).to_be_visible(timeout=15_000)

        upload_kamenice(page)
        expect(page.get_by_text("UP Layer Extractor ·").first).to_be_visible(timeout=30_000)
        expect(page.get_by_text("VECTOR").first).to_be_visible(timeout=10_000)
        expect(page.get_by_text("Features: 1265").first).to_be_visible(timeout=30_000)
        expect(page.get_by_text("Raw fragments: 56642").first).to_be_visible(timeout=30_000)
        expect(page.get_by_text("Plan source: pdf_page_render").first).to_be_visible(timeout=10_000)
        expect(page.get_by_label("Raster validation")).not_to_be_checked(timeout=10_000)
        expect(page.get_by_test_id("viewport-fit-control")).to_be_visible(timeout=10_000)
        expect(page.get_by_test_id("zoom-step-control")).to_be_visible(timeout=10_000)
        if page.locator('button[data-testid^="zoom-step-"]').count() != 10:
            raise AssertionError("UP zoom control does not expose the required 10 zoom steps")
        expect(page.get_by_label("Selected label")).to_be_checked(timeout=10_000)
        page.get_by_test_id("fit-width").click()
        page.get_by_test_id("fit-page").click()

        page.get_by_test_id("color-mode-selector").select_option("source")
        plan_checkbox = page.get_by_label("Plan")
        if plan_checkbox.is_checked():
            plan_checkbox.uncheck()
        expect(page.get_by_text("Plan off").first).to_be_visible(timeout=10_000)
        page.screenshot(path=str(SCREENSHOTS["source_colors"]), full_page=True)
        plan_checkbox.check()
        expect(page.locator('[data-testid="plan-image"]')).to_be_visible(timeout=10_000)
        page.screenshot(path=str(SCREENSHOTS["plan_on"]), full_page=True)

        page.get_by_test_id("color-mode-selector").select_option("artifact")
        page.get_by_label("FID").check()
        page.locator('[data-testid="feature-329"]').click(force=True, timeout=10_000)
        expect(page.get_by_text("Selected Polygon Review")).to_be_visible(timeout=10_000)
        expect(page.get_by_text("Geometry:").first).to_be_visible(timeout=10_000)
        expect(page.get_by_text("geometry_cleanup_algorithm").first).to_be_visible(timeout=10_000)
        expect(page.get_by_test_id("fit-polygon")).to_be_enabled(timeout=10_000)
        page.get_by_test_id("fit-polygon").click()
        expect(page.get_by_test_id("selected-polygon-label")).to_be_visible(timeout=10_000)
        page.get_by_role("button", name="6400%").click()
        page.screenshot(path=str(SCREENSHOTS["up_zoom_steps"]), full_page=True)
        page.get_by_role("button", name="Max").click()
        expect(page.get_by_test_id("selected-polygon-label")).to_be_visible(timeout=10_000)
        page.screenshot(path=str(SCREENSHOTS["artifact_fid329"]), full_page=True)

        page.get_by_role("button", name="Legend", exact=True).click()
        expect(page.get_by_test_id("legend-workbench")).to_be_visible(timeout=15_000)
        if page.get_by_text("Legend Workbench", exact=True).count() != 0:
            raise AssertionError("old Legend Workbench header is still visible")
        expect(page.get_by_text("Legend crop source:").first).to_be_visible(timeout=10_000)
        expect(page.get_by_text("Candidate:").first).to_be_visible(timeout=10_000)
        expect(page.get_by_text("Confidence:").first).to_be_visible(timeout=10_000)
        expect(page.locator('img[alt="Legend crop"]')).to_be_visible(timeout=30_000)
        expect(page.get_by_test_id("legend-fit-control")).to_be_visible(timeout=10_000)
        expect(page.get_by_test_id("legend-fit-page")).to_be_visible(timeout=10_000)
        expect(page.get_by_test_id("legend-fit-width")).to_be_visible(timeout=10_000)
        if page.get_by_test_id("legend-fit-all").count() != 0:
            raise AssertionError("old Fit All control is still rendered")
        expect(page.get_by_test_id("legend-zoom-state")).to_have_text("Fit Page", timeout=10_000)
        if page.get_by_test_id("legend-symbol-overlay").count() != 0:
            raise AssertionError("symbol overlays are visible by default and may cover legend text")
        page.screenshot(path=str(SCREENSHOTS["legend_compact"]), full_page=True)
        page.get_by_test_id("legend-fit-width").click()
        expect(page.get_by_test_id("legend-zoom-state")).to_have_text("Fit Width", timeout=10_000)
        page.get_by_test_id("legend-fit-page").click()
        page.screenshot(path=str(SCREENSHOTS["legend_default"]), full_page=True)

        viewer = page.get_by_test_id("legend-crop-viewer")
        before_zoom = page.get_by_test_id("legend-zoom-state").inner_text()
        viewer.hover()
        page.mouse.wheel(0, -500)
        expect(page.get_by_test_id("legend-zoom-state")).not_to_have_text(before_zoom, timeout=10_000)
        page.get_by_test_id("legend-fit-page").click()
        expect(page.get_by_test_id("legend-zoom-state")).to_have_text("Fit Page", timeout=10_000)

        page.get_by_test_id("legend-list-row-BU").click()
        expect(page.get_by_text("BYDLENÍ VŠEOBECNÉ").first).to_be_visible(timeout=10_000)
        if page.get_by_text('%<"/(1').count() > 0:
            raise AssertionError("garbled raw label text is visible as the main short label")
        page.screenshot(path=str(SCREENSHOTS["legend_label"]), full_page=True)

        inspector = page.get_by_test_id("legend-selected-inspector")
        inspector.get_by_role("button", name="Edit label").click()
        page.get_by_label("Corrected legend label").fill("BYDLENÍ VŠEOBECNÉ - REVIEWED")
        inspector.get_by_role("button", name="Save").click()
        expect(page.get_by_text("label correction saved as manual review record")).to_be_visible(timeout=10_000)
        expect(page.get_by_test_id("legend-selected-label")).to_have_text("BYDLENÍ VŠEOBECNÉ - REVIEWED", timeout=10_000)

        row_bu = page.get_by_test_id("legend-list-row-BU")
        row_bu.focus()
        page.keyboard.press("ArrowDown")
        expect(page.get_by_text("Selected legend item").first).to_be_visible(timeout=10_000)
        page.keyboard.press(" ")
        page.keyboard.press("Enter")
        page.screenshot(path=str(SCREENSHOTS["legend_focused"]), full_page=True)

        page.get_by_test_id("legend-list-row-BH").scroll_into_view_if_needed(timeout=10_000)
        page.get_by_test_id("legend-list-row-BH").click()
        expect(page.get_by_test_id("legend-selected-label")).to_have_text("BYDLENÍ HROMADNÉ", timeout=10_000)
        missing_symbol = page.get_by_text("missing requires review").first
        missing_symbol.scroll_into_view_if_needed(timeout=10_000)
        expect(missing_symbol).to_be_visible(timeout=10_000)
        drag_manual_crop(page)
        page.screenshot(path=str(SCREENSHOTS["manual_crop"]), full_page=True)

        page.get_by_role("button", name="Extraction", exact=True).click()
        expect(page.get_by_test_id("extraction-tab")).to_be_visible(timeout=10_000)
        expect(page.get_by_text("hatch_pattern_segmentation").first).to_be_visible(timeout=10_000)
        expect(page.get_by_text("manual_split_required").first).to_be_visible(timeout=10_000)
        page.screenshot(path=str(SCREENSHOTS["extraction_tab"]), full_page=True)

        browser.close()

    assert_no_browser_errors(console_errors, page_errors, request_urls)
    print("kamenice legend v8.2 ui smoke passed")
    for key, path in SCREENSHOTS.items():
        print(f"{key}={path}")


if __name__ == "__main__":
    main()
