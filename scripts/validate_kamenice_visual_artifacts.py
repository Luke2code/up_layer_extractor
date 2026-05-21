from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.algorithms import extract_vector_candidates


KAMENICE_PDF = next(
    path
    for path in [
        Path("/mnt/c/Users/Me/Downloads/kamenice hlv.pdf"),
        Path("/mnt/c/Users/Me/Downloads/A_PV___KAMENICE___538299___UZ_9_15___HLV.pdf"),
        Path("/mnt/c/stg_db/data/up_import/A_PV/KAMENICE___538299/UZ_9_15/A_PV___KAMENICE___538299___UZ_9_15___HLV.pdf"),
    ]
    if path.exists()
)
REPORT = REPO_ROOT / "docs" / "kamenice_visual_artifacts_validation.json"
HOLE_CLEANUP_REPORT = REPO_ROOT / "docs" / "kamenice_hole_cleanup_diagnostic.json"
HATCH_SPLIT_REPORT = REPO_ROOT / "docs" / "kamenice_hatch_split_diagnostic.json"
FID353_REPORT = REPO_ROOT / "docs" / "kamenice_fid353_diagnostic.json"
SCREENSHOTS = [
    REPO_ROOT / "docs" / "kamenice-v8_1-plan-source-colors.png",
    REPO_ROOT / "docs" / "kamenice-v8_1-plan-snapshot-on.png",
    REPO_ROOT / "docs" / "kamenice-v8_1-artifact-debug-fid329.png",
    REPO_ROOT / "docs" / "kamenice-v8_1-legend-fit-page-default.png",
    REPO_ROOT / "docs" / "kamenice-v8_1-legend-label-cleaned.png",
    REPO_ROOT / "docs" / "kamenice-v8_1-legend-focused-vector-defs.png",
    REPO_ROOT / "docs" / "kamenice-v8_1-manual-legend-crop.png",
    REPO_ROOT / "docs" / "kamenice-v8_2-up-zoom-steps-selected-label.png",
    REPO_ROOT / "docs" / "kamenice-v8_2-legend-compact-candidate-status.png",
    REPO_ROOT / "docs" / "kamenice-v8_2-extraction-method-profile.png",
]


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def health_4101() -> bool:
    try:
        with urlopen("http://127.0.0.1:4101/api/health", timeout=2) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def active_default_8787_hits() -> list[str]:
    roots = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "backend",
        REPO_ROOT / "frontend" / "src",
        REPO_ROOT / "frontend" / "vite.config.ts",
        REPO_ROOT / "scripts",
        REPO_ROOT / "docs" / "VALIDATION_REPORT.md",
        REPO_ROOT / "docs" / "VECTOR_PDF_EXTRACTION_FIX_REPORT.md",
    ]
    hits: list[str] = []
    ignored_parts = {".venv", "node_modules", "__pycache__", "dist"}
    ignored_markers = [
        "direct_8787",
        "active_default_8787",
        "8787_hits",
        "still mention 8787",
        "browser made direct 8787",
        '"8787" not in line',
    ]
    for root in roots:
        paths = [root] if root.is_file() else list(root.rglob("*"))
        for path in paths:
            if ignored_parts.intersection(path.parts):
                continue
            if not path.is_file() or path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".pdf"}:
                continue
            try:
                for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if "8787" not in line:
                        continue
                    if any(marker in line for marker in ignored_markers):
                        continue
                    hits.append(f"{path}:{line_number}")
            except OSError:
                continue
    return hits


def feature_props(features: list[dict[str, Any]], fid: int) -> dict[str, Any] | None:
    return next(((row.get("properties") or {}) for row in features if (row.get("properties") or {}).get("FID") == fid), None)


def feature_probe(props: dict[str, Any] | None, fid: int) -> dict[str, Any]:
    if props is None:
        return {
            "status": "not_found",
            "requested_fid": fid,
            "reason": "FID is not stable in the current merged output",
        }
    return {
        "status": "found",
        "fid": fid,
        "proposed_class": props.get("proposed_CLASS"),
        "source_text_nearby": props.get("source_text_nearby"),
        "manual_split_required": props.get("manual_split_required"),
        "manual_split_reason": props.get("manual_split_reason"),
        "export_eligible": props.get("export_eligible"),
        "export_blocking_reason": props.get("export_blocking_reason"),
        "artifact_flags": props.get("artifact_flags"),
        "geometry_decision": props.get("geometry_decision"),
        "hole_cleanup": props.get("hole_cleanup"),
        "hole_type_counts": props.get("hole_type_counts"),
        "cleaned_candidate_available": props.get("cleaned_candidate_available"),
        "cleaned_candidate_metadata": (props.get("cleaned_candidate_geometry") or {}).get("review_candidate_metadata") if isinstance(props.get("cleaned_candidate_geometry"), dict) else None,
    }


def validate() -> dict[str, Any]:
    start = time.perf_counter()
    failures: list[str] = []
    if not health_4101():
        fail("backend /api/health is not available on 127.0.0.1:4101", failures)
    hits = active_default_8787_hits()
    if hits:
        fail("active default files still mention 8787: " + ", ".join(hits), failures)

    collection = extract_vector_candidates(KAMENICE_PDF, source_url=f"visual-validation:{KAMENICE_PDF.name}")
    artifact = collection.get("artifact_diagnostics") or {}
    legend_candidates = collection.get("legend_candidates") or []
    fragment_roles = collection.get("fragment_role_stats") or {}
    task_stats = collection.get("task_stats") or {}
    features = collection.get("features") or []
    extraction_profile = collection.get("up_extraction_profile") or {}
    selected = next(((row.get("properties") or {}) for row in features if (row.get("properties") or {}).get("FID") == 329), None)
    fid329_reproducible = selected is not None
    if selected is None:
        selected = (features[0].get("properties") if features else {}) or {}
    fid337 = feature_props(features, 337)
    fid353 = feature_props(features, 353)

    if collection.get("primary_extraction_mode") != "merged_polygons":
        fail(f"Kamenice mode is {collection.get('primary_extraction_mode')!r}; expected merged_polygons", failures)
    if int(collection.get("raw_fragment_count") or 0) < 50000:
        fail("raw fragment count is below Kamenice tessellation baseline", failures)
    if int(collection.get("feature_count") or len(features)) != 1265:
        fail(f"merged polygon count changed unexpectedly: {collection.get('feature_count') or len(features)}", failures)
    if not collection.get("plan_snapshot_available"):
        fail("Kamenice PDF has no rendered Plan snapshot", failures)
    if not collection.get("plan_snapshot_url"):
        fail("Kamenice PDF Plan snapshot URL is missing", failures)
    if not (collection.get("plan_snapshot_transform") or {}).get("page_to_image_scale_x"):
        fail("Kamenice PDF Plan alignment transform is missing", failures)
    if not artifact:
        fail("artifact_diagnostics are missing", failures)
    if not legend_candidates:
        fail("legend_candidates are missing", failures)
    if legend_candidates and not any(row.get("selected") for row in legend_candidates):
        fail("no legend candidate is selected", failures)
    if legend_candidates and not all("signals" in row and "score" in row for row in legend_candidates):
        fail("legend candidates do not include score/signals evidence", failures)
    if not fragment_roles.get("fragment_role_counts"):
        fail("fragment role counts are missing", failures)
    if not extraction_profile:
        fail("up_extraction_profile is missing", failures)
    if extraction_profile and extraction_profile.get("algorithm") != "method_aware_extraction_profile_v8_2":
        fail(f"unexpected extraction profile algorithm: {extraction_profile.get('algorithm')!r}", failures)
    method_names = {row.get("method") for row in extraction_profile.get("method_rows") or []}
    for method in ["fill_style_polygonization", "hatch_pattern_segmentation", "dotted_boundary_segmentation", "thick_line_boundary_segmentation", "text_anchor_region_assignment", "legend_style_mapping", "raster_assisted_segmentation", "manual_split_required"]:
        if method not in method_names:
            fail(f"extraction method profile is missing {method}", failures)
    if extraction_profile and int(extraction_profile.get("hatch_candidate_count") or 0) <= 0:
        fail("hatch candidate evidence is missing from extraction profile", failures)
    if extraction_profile and extraction_profile.get("export_status") != "blocked":
        fail(f"expected export_status blocked while manual split/artifact review remains, got {extraction_profile.get('export_status')!r}", failures)
    if artifact.get("trusted_white_or_background_feature_count", 0) > 0:
        fail("white/background artifacts are present in trusted merged output", failures)
    if artifact.get("max_spike_score", 0) >= 0.75 and artifact.get("artifact_requires_review_feature_count", 0) <= 0:
        fail("high spike/needle score remains without artifact_requires_review flag", failures)
    for key in [
        "white_fill_fragment_count",
        "white_fill_fragment_area",
        "background_mask_candidate_count",
        "rectangular_hole_count",
        "rectangular_hole_area_ratio",
        "holes_removed_as_artifacts_count",
        "holes_kept_count",
        "hole_review_required_count",
        "needle_count",
        "sliver_component_count",
        "thin_corridor_count",
        "triangular_void_count",
        "small_void_count",
        "void_area_ratio",
        "void_requires_review_count",
        "spike_review_required_count",
        "geometry_cleanup_algorithm",
        "hole_type_counts",
        "hole_cleanup_candidate_feature_count",
        "hole_cleanup_removed_hole_count",
        "hole_cleanup_review_required_hole_count",
    ]:
        if key not in artifact and key not in task_stats:
            fail(f"artifact metric {key} is missing", failures)
    for key in ["raw_CLASS", "proposed_CLASS", "classification_reason", "artifact_flags", "export_blocking_reason", "display_fill_hex", "display_color_source", "source_fill_hex", "geometry_decision", "geometry_decision_reason", "artifact_component_count", "component_count_before", "component_count_after", "hole_cleanup", "hole_type_counts", "manual_split_required"]:
        if key not in selected:
            fail(f"selected polygon field {key} is missing", failures)
    if selected.get("proposed_CLASS") == "UNMAPPED" and not selected.get("classification_reason"):
        fail("selected polygon is unmapped without explicit reason", failures)
    if selected.get("display_color_source") == "fallback_unmapped" and selected.get("source_fill_hex"):
        fail("selected polygon ignored available source color evidence")
    if not fid329_reproducible:
        fail("FID 329 diagnostic is not reproducible in the current merged output", failures)
    if (
        (selected.get("spike_score") or 0) >= 0.55
        or (selected.get("void_requires_review_count") or 0) > 0
        or (selected.get("thin_corridor_count") or 0) > 0
    ) and "artifact_requires_review" not in (selected.get("artifact_flags") or []):
        fail("FID/problem feature has artifact scores without artifact_requires_review flag", failures)
    missing_screenshots = [str(path) for path in SCREENSHOTS if not path.exists() or path.stat().st_size <= 0]
    if missing_screenshots:
        fail("required screenshot evidence is missing: " + ", ".join(missing_screenshots), failures)

    return {
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "runtime_ms": round((time.perf_counter() - start) * 1000),
        "backend_4101_health": health_4101(),
        "active_default_8787_hits": hits,
        "pdf": str(KAMENICE_PDF),
        "primary_extraction_mode": collection.get("primary_extraction_mode"),
        "raw_fragment_count": collection.get("raw_fragment_count"),
        "primary_feature_count": collection.get("feature_count") or len(features),
        "artifact_diagnostics": artifact,
        "up_extraction_profile": extraction_profile,
        "legend_candidates": legend_candidates,
        "fragment_role_counts": fragment_roles.get("fragment_role_counts"),
        "plan_snapshot": {
            "available": collection.get("plan_snapshot_available"),
            "url": collection.get("plan_snapshot_url"),
            "source": collection.get("plan_snapshot_source"),
            "transform": collection.get("plan_snapshot_transform"),
        },
        "fid329_reproducible": fid329_reproducible,
        "selected_polygon_probe": {key: selected.get(key) for key in ["FID", "raw_CLASS", "proposed_CLASS", "classification_reason", "artifact_flags", "export_blocking_reason", "display_fill_hex", "display_color_source", "source_fill_hex", "geometry_decision", "geometry_decision_reason", "artifact_component_count", "component_count_before", "component_count_after", "triangular_void_count", "small_void_count", "void_requires_review_count", "hole_cleanup", "hole_type_counts", "manual_split_required", "manual_split_reason"]},
        "fid337_probe": feature_probe(fid337, 337),
        "fid353_probe": feature_probe(fid353, 353),
        "hole_cleanup_report": {
            "status": "review_candidate_only",
            "raw_geometry_preserved": True,
            "algorithm": "review_candidate_remove_label_mask_white_background_hatch_grid_holes_v8_2",
            "artifact_hole_type_counts": artifact.get("hole_type_counts"),
            "removed_hole_count": artifact.get("hole_cleanup_removed_hole_count"),
            "review_required_hole_count": artifact.get("hole_cleanup_review_required_hole_count"),
            "candidate_feature_count": artifact.get("hole_cleanup_candidate_feature_count"),
            "sample_features": [feature_probe(feature_props(features, fid), fid) for fid in [329, 337, 353]],
        },
        "hatch_split_report": {
            "status": "manual_split_required" if extraction_profile.get("manual_split_required_count") else "candidate_only",
            "profile_algorithm": extraction_profile.get("algorithm"),
            "export_status": extraction_profile.get("export_status"),
            "manual_split_required_count": extraction_profile.get("manual_split_required_count"),
            "hatch_candidate_count": extraction_profile.get("hatch_candidate_count"),
            "dotted_boundary_candidate_count": extraction_profile.get("dotted_boundary_candidate_count"),
            "thick_boundary_candidate_count": extraction_profile.get("thick_boundary_candidate_count"),
            "method_rows": extraction_profile.get("method_rows"),
            "manual_split_feature_ids_sample": extraction_profile.get("manual_split_feature_ids_sample"),
            "risk": "automatic vector-only hatch/dotted boundary semantic separation is not yet reliable enough for clean export",
        },
        "screenshots": [str(path) for path in SCREENSHOTS],
    }


def main() -> None:
    result = validate()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    HOLE_CLEANUP_REPORT.write_text(json.dumps(result["hole_cleanup_report"], ensure_ascii=False, indent=2), encoding="utf-8")
    HATCH_SPLIT_REPORT.write_text(json.dumps(result["hatch_split_report"], ensure_ascii=False, indent=2), encoding="utf-8")
    if result["fid353_probe"]["status"] == "found":
        FID353_REPORT.write_text(json.dumps(result["fid353_probe"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "passed":
        sys.exit(1)


if __name__ == "__main__":
    main()
