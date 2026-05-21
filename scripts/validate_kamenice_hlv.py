from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.algorithms import extract_vector_candidates


DEFAULT_PDF = Path("/mnt/c/Users/Me/Downloads/kamenice hlv.pdf")
DEFAULT_PDF_FALLBACKS = [
    DEFAULT_PDF,
    Path("/mnt/c/Users/Me/Downloads/A_PV___KAMENICE___538299___UZ_9_15___HLV.pdf"),
    Path("/mnt/c/stg_db/data/up_import/A_PV/KAMENICE___538299/UZ_9_15/A_PV___KAMENICE___538299___UZ_9_15___HLV.pdf"),
]
DEFAULT_JSON_OUT = REPO_ROOT / "docs" / "kamenice_hlv_validation.json"


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def validate(path: Path) -> dict[str, Any]:
    start = time.perf_counter()
    collection = extract_vector_candidates(path, source_url=f"validation:{path.name}")
    runtime_ms = round((time.perf_counter() - start) * 1000)
    tessellation = collection.get("tessellation_metrics") or {}
    merge_stats = collection.get("merge_stats") or {}
    legend_crops = collection.get("legend_crops") or []
    legend_candidates = collection.get("legend_candidates") or []
    legend_rows = collection.get("legend_rows") or []
    legend_items = collection.get("legend_items") or []
    legend_symbols = collection.get("legend_symbols") or []
    legend_mapping_stats = collection.get("legend_mapping_stats") or {}
    artifact_diagnostics = collection.get("artifact_diagnostics") or {}
    fragment_role_stats = collection.get("fragment_role_stats") or {}
    feature_proposal_stats = collection.get("feature_proposal_stats") or {}
    legend_vector_defs = [row for row in collection.get("vector_definitions") or [] if row.get("legend_item_id")]
    pipeline_steps = {row.get("step_name"): row for row in collection.get("pipeline_traces") or []}
    failures: list[str] = []

    raw_count = int(collection.get("raw_fragment_count") or tessellation.get("raw_fragment_count") or 0)
    primary_count = len(collection.get("features") or [])
    if raw_count < 50000:
        fail(f"expected Kamenice raw fragment baseline above 50k, got {raw_count}", failures)
    if collection.get("primary_extraction_mode") != "merged_polygons":
        fail(f"primary_extraction_mode is {collection.get('primary_extraction_mode')!r}, expected merged_polygons", failures)
    if not tessellation.get("tessellated_fill_detected"):
        fail("tessellated_fill_detected is false", failures)
    if "tessellated_fill_merge" not in pipeline_steps:
        fail("pipeline step tessellated_fill_merge is missing", failures)
    if merge_stats.get("merge_algorithm") != "vector_tessellated_fill_merge_v1":
        fail(f"merge algorithm is {merge_stats.get('merge_algorithm')!r}", failures)
    if not merge_stats.get("raw_features_are_debug_only"):
        fail("raw_features_are_debug_only is false", failures)
    if primary_count <= 0:
        fail("no primary merged polygons emitted", failures)
    if primary_count >= raw_count:
        fail(f"primary feature count {primary_count} is not lower than raw fragment count {raw_count}", failures)
    if raw_count and primary_count and (raw_count / primary_count) < 5:
        fail(f"raw-to-primary ratio {raw_count / primary_count:.2f} is too low for a tessellation fix", failures)
    if not collection.get("raw_fragment_debug_sample"):
        fail("raw_fragment_debug_sample is missing", failures)
    if not collection.get("plan_snapshot_available"):
        fail("PDF page Plan snapshot is missing", failures)
    if not collection.get("plan_snapshot_url"):
        fail("PDF page Plan snapshot URL is missing", failures)
    if not (collection.get("plan_snapshot_transform") or {}).get("page_to_image_scale_x"):
        fail("PDF page Plan snapshot transform is missing", failures)
    if not any(row.get("image_artifact_path_or_url") for row in legend_crops):
        fail("legend autocrop image artifact is missing", failures)
    if not any(row.get("page_to_image_transform") for row in legend_crops):
        fail("legend crop page-to-image transform is missing", failures)
    if not legend_candidates:
        fail("legend_candidates are missing", failures)
    if legend_candidates and not any(row.get("selected") for row in legend_candidates):
        fail("legend candidate ranking did not select an autocrop candidate", failures)
    if legend_candidates and not all(row.get("signals") and row.get("score") is not None for row in legend_candidates):
        fail("legend candidates are missing score/signals evidence", failures)
    for row in legend_crops:
        artifact = row.get("image_artifact_path_or_url")
        if artifact and not Path(str(artifact)).exists():
            fail(f"legend autocrop artifact path does not exist: {artifact}", failures)
    if not collection.get("manual_legend_crop_fallbacks"):
        fail("manual legend crop fallback record is missing", failures)
    if not legend_items:
        fail("legend_items are missing", failures)
    if not legend_symbols:
        fail("legend_symbols are missing", failures)
    if not legend_vector_defs:
        fail("legend-linked vector definition rows are missing", failures)
    if "legend_item_to_vector_def_split" not in pipeline_steps:
        fail("pipeline step legend_item_to_vector_def_split is missing", failures)
    target_codes = {row.get("code_text") or row.get("target_code") for row in legend_rows}
    for required in ["BU", "SX", "BX.c", "BX.p", "BX.r", "RI", "SV"]:
        if required not in target_codes:
            fail(f"legend row for {required} is missing", failures)
    paired_items = [row for row in legend_items if row.get("normal_vector_def_row_count") == 2]
    if not paired_items:
        fail("no legend item produced paired STAV/NAVRH vector definition rows", failures)
    fabricated_missing = [
        row
        for row in legend_vector_defs
        if row.get("symbol_role") in {"stav_stabil", "navrh"} and not row.get("symbol_bbox_page_pt")
    ]
    if fabricated_missing:
        fail("normal vector_def rows were fabricated for missing expected symbols", failures)
    if legend_mapping_stats.get("checkbox_to_vector_def_wiring_count", 0) <= 0:
        fail("checkbox-to-vector_def wiring count is zero", failures)
    if not collection.get("task_stats"):
        fail("task_stats are missing", failures)
    if not collection.get("correction_tasks"):
        fail("correction_tasks are missing", failures)
    if not artifact_diagnostics:
        fail("artifact_diagnostics are missing", failures)
    if not fragment_role_stats.get("fragment_role_counts"):
        fail("fragment role classification is missing", failures)
    if "fragment_role_classification" not in pipeline_steps:
        fail("pipeline step fragment_role_classification is missing", failures)
    if "feature_proposal_annotation" not in pipeline_steps:
        fail("pipeline step feature_proposal_annotation is missing", failures)
    if artifact_diagnostics.get("trusted_white_or_background_feature_count", 0) > 0:
        fail("white/background features are present in trusted primary output", failures)
    if artifact_diagnostics.get("max_spike_score", 0) >= 0.75 and artifact_diagnostics.get("artifact_requires_review_feature_count", 0) <= 0:
        fail("high spike score is not paired with artifact review flags", failures)
    for key in ["triangular_void_count", "small_void_count", "void_area_ratio", "void_requires_review_count", "spike_review_required_count", "geometry_cleanup_algorithm"]:
        if key not in artifact_diagnostics:
            fail(f"V7 artifact diagnostic {key} is missing", failures)
    if feature_proposal_stats.get("feature_proposal_count", 0) <= 0:
        fail("selected polygon proposal annotations are missing", failures)
    selected = (collection.get("features") or [{}])[0].get("properties") or {}
    for key in ["raw_CLASS", "proposed_CLASS", "classification_reason", "export_blocking_reason", "artifact_flags", "display_fill_hex", "display_color_source", "source_fill_hex", "geometry_decision", "geometry_decision_reason", "artifact_component_count", "component_count_before", "component_count_after"]:
        if key not in selected:
            fail(f"selected polygon property {key} is missing", failures)
    bad_labels = [item for item in legend_items if item.get("label_text_status") in {"garbled", "manual_required"} and item.get("label_text_display") == item.get("label_text_raw")]
    if bad_labels:
        fail("garbled raw legend labels are still used as display labels", failures)

    return {
        "pdf": str(path),
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "runtime_ms": runtime_ms,
        "raw_fragment_count": raw_count,
        "primary_feature_count": primary_count,
        "raw_to_primary_ratio": round(raw_count / max(primary_count, 1), 3),
        "primary_extraction_mode": collection.get("primary_extraction_mode"),
        "tessellated_fill_detected": tessellation.get("tessellated_fill_detected"),
        "tessellated_fill_score": tessellation.get("tessellated_fill_score"),
        "median_fragment_area": tessellation.get("median_fragment_area"),
        "median_fragment_bbox_height": tessellation.get("median_fragment_bbox_height"),
        "triangular_fragment_ratio": tessellation.get("triangular_fragment_ratio"),
        "tiny_fragment_ratio": tessellation.get("tiny_fragment_ratio"),
        "merge_algorithm": merge_stats.get("merge_algorithm"),
        "merge_strategy": merge_stats.get("merge_strategy"),
        "merged_group_count": merge_stats.get("merged_group_count"),
        "merge_runtime_ms": merge_stats.get("merge_runtime_ms"),
        "plan_snapshot_available": collection.get("plan_snapshot_available"),
        "plan_snapshot_url": collection.get("plan_snapshot_url"),
        "plan_snapshot_source": collection.get("plan_snapshot_source"),
        "legend_crop_artifacts": [row.get("image_artifact_path_or_url") for row in legend_crops if row.get("image_artifact_path_or_url")],
        "legend_crop_urls": [row.get("image_artifact_url") for row in legend_crops if row.get("image_artifact_url")],
        "legend_candidates": legend_candidates,
        "legend_overlay_transform_count": legend_mapping_stats.get("legend_overlay_transform_count", 0),
        "legend_row_count": len(legend_rows),
        "legend_column_count": legend_mapping_stats.get("legend_column_count", 0),
        "legend_item_count": len(legend_items),
        "legend_symbol_count": len(legend_symbols),
        "legend_vector_def_count": len(legend_vector_defs),
        "two_row_vector_def_split_count": legend_mapping_stats.get("two_row_vector_def_split_count", 0),
        "ignored_extra_rectangle_count": legend_mapping_stats.get("ignored_extra_symbol_count", 0),
        "missing_expected_symbol_count": legend_mapping_stats.get("missing_expected_symbol_count", 0),
        "checkbox_to_vector_def_wiring_count": legend_mapping_stats.get("checkbox_to_vector_def_wiring_count", 0),
        "focused_legend_item_count": legend_mapping_stats.get("focused_legend_item_count", 0),
        "checked_legend_item_count": legend_mapping_stats.get("checked_legend_item_count", 0),
        "spatial_associations_created": (collection.get("spatial_association_stats") or {}).get("feature_text_association_count"),
        "target_classification_proposal_count": len([row for row in collection.get("classification_proposals") or [] if row.get("is_inscope_bydleni_related")]),
        "requires_review_count": len([row for row in collection.get("classification_proposals") or [] if row.get("requires_review")]),
        "exportable_target_count": legend_mapping_stats.get("exportable_target_count", 0),
        "fragment_role_counts": fragment_role_stats.get("fragment_role_counts"),
        "white_fill_fragment_count": artifact_diagnostics.get("white_fill_fragment_count"),
        "background_mask_candidate_count": artifact_diagnostics.get("background_mask_candidate_count"),
        "trusted_white_or_background_feature_count": artifact_diagnostics.get("trusted_white_or_background_feature_count"),
        "rectangular_hole_count": artifact_diagnostics.get("rectangular_hole_count"),
        "rectangular_hole_area_ratio": artifact_diagnostics.get("rectangular_hole_area_ratio"),
        "holes_removed_as_artifacts_count": artifact_diagnostics.get("holes_removed_as_artifacts_count"),
        "holes_kept_count": artifact_diagnostics.get("holes_kept_count"),
        "hole_review_required_count": artifact_diagnostics.get("hole_review_required_count"),
        "triangular_void_count": artifact_diagnostics.get("triangular_void_count"),
        "small_void_count": artifact_diagnostics.get("small_void_count"),
        "void_area_ratio": artifact_diagnostics.get("void_area_ratio"),
        "void_removed_as_artifact_count": artifact_diagnostics.get("void_removed_as_artifact_count"),
        "void_kept_count": artifact_diagnostics.get("void_kept_count"),
        "void_requires_review_count": artifact_diagnostics.get("void_requires_review_count"),
        "max_spike_score": artifact_diagnostics.get("max_spike_score"),
        "spike_count": artifact_diagnostics.get("spike_count"),
        "spike_fixed_count": artifact_diagnostics.get("spike_fixed_count"),
        "spike_review_required_count": artifact_diagnostics.get("spike_review_required_count"),
        "needle_count": artifact_diagnostics.get("needle_count"),
        "sliver_component_count": artifact_diagnostics.get("sliver_component_count"),
        "thin_corridor_count": artifact_diagnostics.get("thin_corridor_count"),
        "geometry_cleanup_algorithm": artifact_diagnostics.get("geometry_cleanup_algorithm"),
        "artifact_requires_review_feature_count": artifact_diagnostics.get("artifact_requires_review_feature_count"),
        "feature_proposal_count": feature_proposal_stats.get("feature_proposal_count"),
        "feature_unmapped_count": feature_proposal_stats.get("unmapped_feature_count"),
        "pipeline_steps": list(pipeline_steps),
        "implementation_approaches_recorded": [
            "baseline_raw_positive_polygon_count_v1",
            "solid_dash_pattern_normalization_v2",
            "right_panel_text_density_region_v1",
            "stripe_fragment_detector_v1",
            "vector_tessellated_fill_merge_v1",
            "raw_fragment_false_success_gate_v1",
            "right_panel_autocrop_render_v1",
            "target_left_legend_autocrop_render_v1",
            "target_code_row_inventory_v1",
            "target_code_row_symbol_split_v1",
            "legend_item_two_symbol_vector_def_split_v1",
            "fake_legend_provider_v1",
            "bbox_contains_or_nearest_target_text_v1",
            "operator_bbox_fallback_v1",
            "fragment_role_classification_v1",
            "visual_artifact_diagnostics_v1",
            "selected_polygon_proposal_annotation_v1",
            "pymupdf_page_render_snapshot_v1",
            "display_color_source_style_v1",
            "void_artifact_review_flagging_v1",
            "legend_label_quality_gate_v1",
            "legend_candidate_evidence_ranker_v8_1",
            "review_candidate_remove_small_triangular_voids_v8_1",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the Kamenice HLV tessellated vector extraction fix.")
    parser.add_argument("--pdf", default=str(DEFAULT_PDF))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    args = parser.parse_args()

    path = Path(args.pdf)
    if str(path) == str(DEFAULT_PDF) and not path.exists():
        path = next((candidate for candidate in DEFAULT_PDF_FALLBACKS if candidate.exists()), path)
    if not path.exists():
        raise SystemExit(f"missing PDF: {path}")
    result = validate(path)
    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "passed":
        sys.exit(1)


if __name__ == "__main__":
    main()
