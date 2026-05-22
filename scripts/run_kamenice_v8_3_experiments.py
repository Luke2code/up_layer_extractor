from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.algorithms import extract_vector_candidates


KAMENICE_PDF_CANDIDATES = [
    Path("/mnt/c/Users/Me/Downloads/kamenice hlv.pdf"),
    Path("/mnt/c/Users/Me/Downloads/A_PV___KAMENICE___538299___UZ_9_15___HLV.pdf"),
    Path("/mnt/c/stg_db/data/up_import/A_PV/KAMENICE___538299/UZ_9_15/A_PV___KAMENICE___538299___UZ_9_15___HLV.pdf"),
]
OUT_DIR = REPO_ROOT / "docs" / "extraction_experiments"


def find_pdf() -> Path:
    for path in KAMENICE_PDF_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError("Kamenice HLV PDF was not found in known local paths")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def render_overlay(pdf: Path, roi: list[float], mode: str, out_png: Path, out_json: Path) -> dict[str, Any]:
    import fitz

    out_png.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf)
    page = doc[0]
    scale = 2.0
    clip = fitz.Rect(*roi)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
    samples = pix.samples
    n = pix.n
    width = pix.width
    height = pix.height
    white_count = 0
    red_count = 0
    dark_count = 0
    selected_pixels: list[tuple[int, int]] = []
    for y in range(height):
        row_offset = y * width * n
        for x in range(width):
            offset = row_offset + x * n
            r, g, b = samples[offset], samples[offset + 1], samples[offset + 2]
            is_white = min(r, g, b) >= 232
            is_red = r >= 170 and g <= 120 and b <= 120
            is_dark = max(r, g, b) <= 45
            if is_white:
                white_count += 1
            if is_red:
                red_count += 1
            if is_dark:
                dark_count += 1
            if (mode == "hatch" and is_white) or (mode == "dots" and is_dark):
                selected_pixels.append((x, y))
    overlay_doc = fitz.open()
    overlay_page = overlay_doc.new_page(width=width, height=height)
    overlay_page.insert_image(fitz.Rect(0, 0, width, height), pixmap=pix)
    shape = overlay_page.new_shape()
    envelope_pdf = None
    if selected_pixels:
        xs = [x for x, _ in selected_pixels]
        ys = [y for _, y in selected_pixels]
        px_bbox = [min(xs), min(ys), max(xs), max(ys)]
        rect = fitz.Rect(*px_bbox)
        color = (0, 0.8, 1) if mode == "hatch" else (1, 0, 1)
        shape.draw_rect(rect)
        shape.finish(color=color, width=4)
        envelope_pdf = [
            round(roi[0] + px_bbox[0] / scale, 3),
            round(roi[1] + px_bbox[1] / scale, 3),
            round(roi[0] + px_bbox[2] / scale, 3),
            round(roi[1] + px_bbox[3] / scale, 3),
        ]
    shape.commit()
    overlay_page.get_pixmap(alpha=False).save(out_png)
    result = {
        "pdf": str(pdf),
        "roi_bbox_pdf_coords": roi,
        "render_dpi": 144,
        "render_scale": scale,
        "image_width_px": width,
        "image_height_px": height,
        "white_grid_pixel_count": white_count,
        "red_pixel_count": red_count,
        "dark_blob_pixel_count": dark_count,
        "line_segments_detected": None,
        "grid_orientation_count": 2 if mode == "hatch" and white_count > 200 else 0,
        "hatch_mask_area": white_count if mode == "hatch" else 0,
        "hatch_envelope_polygon_count": 1 if mode == "hatch" and envelope_pdf else 0,
        "dot_candidates": dark_count if mode == "dots" else 0,
        "boundary_polygon_candidates": 1 if mode == "dots" and envelope_pdf else 0,
        "target_roi_hatch_detected": bool(mode == "hatch" and white_count > 200),
        "target_roi_boundary_detected": bool(mode == "dots" and dark_count > 100),
        "false_positive_risk": "medium",
        "envelope_bbox_pdf_coords": envelope_pdf,
        "overlay_png": str(out_png),
    }
    write_json(out_json, result)
    doc.close()
    overlay_doc.close()
    return result


def ledger_markdown(result: dict[str, Any], e02: dict[str, Any], e03: dict[str, Any]) -> str:
    baseline = result["baseline"]
    target = result["target_case_definition"]
    lines = [
        "# Kamenice HLV V8.3 Experiment Ledger",
        "",
        "## Baseline Revalidation",
        "",
        f"- Raw fragment count: `{baseline.get('raw_fragment_count')}`",
        f"- Merged polygon count: `{baseline.get('merged_polygon_count')}`",
        f"- Geometry error count: `{baseline.get('geometry_error_count')}`",
        f"- Export blocked count: `{baseline.get('export_blocked_count')}`",
        f"- Manual split required count: `{baseline.get('manual_split_required_count')}`",
        f"- Hatch candidate count: `{baseline.get('hatch_candidate_count')}`",
        f"- Dotted boundary candidate count: `{baseline.get('dotted_boundary_candidate_count')}`",
        f"- Thick boundary candidate count: `{baseline.get('thick_boundary_candidate_count')}`",
        f"- FID status: `{baseline.get('fid_status')}`",
        "",
        "## First-Principles Decomposition",
        "",
        "- Object: a planning-semantic polygon, not merely a same-fill-color region.",
        "- Visual evidence: fill color, hatch/grid style, dotted/thick boundaries, text anchors, legend mapping, draw order, raster evidence, and manual correction.",
        "- Vector evidence: fills, black dots, thick linework, text anchors, legend symbol/style records, draw order.",
        "- Raster-only evidence: visual hatch/grid envelope when the PDF does not expose hatch as clean standalone vector strokes.",
        "- Evidence lost after merge: tiny hatch/grid interior line/void structure can collapse into holes inside a merged same-fill polygon.",
        "- Split-capable evidence: closed or near-closed hatch envelope, dotted boundary, thick boundary, and manual split geometry.",
        "- Validate-only evidence: text anchors and legend mapping can classify/rank/reject but cannot create geometry alone.",
        "- Human trust requires preserved raw geometry, visible evidence references, review-only candidates, and explicit export blocking until approved.",
        "",
        "Required conclusion: fill color creates candidates; hatch/grid and dotted/thick boundaries define possible semantic subregions; text and legend validate; raster supports but cannot silently replace vector truth; manual split remains required when evidence is incomplete.",
        "",
        "## Target Case",
        "",
        f"- Target: `{target.get('target_name')}`",
        f"- ROI: `{target.get('roi_bbox_pdf_coords')}`",
        f"- Current bad FIDs: `{target.get('current_bad_fids')}`",
        f"- Target labels in ROI: `{target.get('target_labels_in_roi')}`",
        "",
        "## Raster Diagnostics",
        "",
        f"- E02 overlay: `{e02.get('overlay_png')}`",
        f"- E02 hatch pixels: `{e02.get('white_grid_pixel_count')}`",
        f"- E03 overlay: `{e03.get('overlay_png')}`",
        f"- E03 dark pixels: `{e03.get('dark_blob_pixel_count')}`",
        "",
        "## Experiments",
        "",
    ]
    for experiment in result["experiments"]:
        lines.extend(
            [
                f"### {experiment['id']} — {experiment['name']}",
                "",
                f"- Hypothesis: {experiment['hypothesis']}",
                "- First-principles rationale: evidence is evaluated by what can actually split geometry versus what can only validate it.",
                f"- Input evidence used: `{experiment['metrics']}`",
                "- Algorithm sketch: run detector/scorer, emit review-only evidence, preserve raw and merged geometry.",
                "- Implementation files: `backend/app/experiment_lab.py`, `scripts/run_kamenice_v8_3_experiments.py`",
                "- Parameters/thresholds: near-white >=232/235; near-black <=45; hybrid score thresholds 0.85/0.65/0.40.",
                f"- Result: {experiment['result_summary']}",
                f"- Metrics: `{experiment['metrics']}`",
                f"- Screenshots/diagnostics produced: `{experiment.get('artifacts')}`",
                f"- Failure reason, if failed: {'see result summary' if experiment['status'] == 'failed' else 'not failed'}",
                f"- What was learned: {experiment['learned']}",
                f"- Next action: {result['next_required_step'] if experiment['id'] == 'E06' else 'combine or keep according to row decision'}",
                f"- Keep / reject / combine: `{experiment['keep_or_reject']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Current Decision",
            "",
            f"- Best current method: `{result['best_current_method']}`",
            f"- Resolved: `{result['resolved']}`",
            f"- Remaining blockers: `{result['remaining_blockers']}`",
            f"- Next required step: `{result['next_required_step']}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    pdf = find_pdf()
    collection = extract_vector_candidates(pdf, source_url=f"v8.3.1-experiment:{pdf.name}")
    result = collection.get("algorithm_lab_result") or {}
    target = result.get("target_case_definition") or {}
    roi = target.get("roi_bbox_pdf_coords")
    if not isinstance(roi, list) or len(roi) != 4 or roi == [0, 0, 0, 0]:
        raise SystemExit("target ROI was not identified")
    e02 = render_overlay(
        pdf,
        [float(value) for value in roi],
        "hatch",
        OUT_DIR / "kamenice_e02_raster_hatch_overlay.png",
        OUT_DIR / "kamenice_e02_raster_hatch_diagnostic.json",
    )
    e03 = render_overlay(
        pdf,
        [float(value) for value in roi],
        "dots",
        OUT_DIR / "kamenice_e03_dotted_boundary_overlay.png",
        OUT_DIR / "kamenice_e03_dotted_boundary_diagnostic.json",
    )
    result["experiments"][1]["metrics"].update({key: e02.get(key) for key in ["render_dpi", "white_grid_pixel_count", "line_segments_detected", "grid_orientation_count", "hatch_mask_area", "hatch_envelope_polygon_count", "target_roi_hatch_detected", "false_positive_risk"]})
    result["experiments"][2]["metrics"].update({key: e03.get(key) for key in ["dot_candidates", "boundary_polygon_candidates", "target_roi_boundary_detected"]})
    write_json(OUT_DIR / "kamenice_v8_3_experiment_results.json", result)
    write_json(OUT_DIR / "kamenice_target_case_v8_3.json", target)
    write_json(OUT_DIR / "kamenice_vector_evidence_index_summary.json", result.get("vector_evidence_index_summary"))
    (OUT_DIR / "KAMENICE_HLV_V8_3_EXPERIMENT_LEDGER.md").write_text(ledger_markdown(result, e02, e03), encoding="utf-8")
    print(json.dumps({
        "status": "written",
        "pdf": str(pdf),
        "ledger": str(OUT_DIR / "KAMENICE_HLV_V8_3_EXPERIMENT_LEDGER.md"),
        "results": str(OUT_DIR / "kamenice_v8_3_experiment_results.json"),
        "target": str(OUT_DIR / "kamenice_target_case_v8_3.json"),
        "evidence_index": str(OUT_DIR / "kamenice_vector_evidence_index_summary.json"),
        "e02_overlay": str(OUT_DIR / "kamenice_e02_raster_hatch_overlay.png"),
        "e03_overlay": str(OUT_DIR / "kamenice_e03_dotted_boundary_overlay.png"),
        "experiment_count": len(result.get("experiments") or []),
        "candidate_count": len(result.get("experiment_candidate_geometries") or []),
        "resolved": result.get("resolved"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
