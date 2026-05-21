from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.algorithms import extract_vector_candidates
from backend.app.geometry import geometry_area, geometry_bbox


KAMENICE_PDF_CANDIDATES = [
    Path("/mnt/c/Users/Me/Downloads/kamenice hlv.pdf"),
    Path("/mnt/c/Users/Me/Downloads/A_PV___KAMENICE___538299___UZ_9_15___HLV.pdf"),
    Path("/mnt/c/stg_db/data/up_import/A_PV/KAMENICE___538299/UZ_9_15/A_PV___KAMENICE___538299___UZ_9_15___HLV.pdf"),
]


def find_pdf() -> Path:
    for path in KAMENICE_PDF_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError("Kamenice HLV PDF was not found in known local paths")


def ring_perimeter(points: list[Any]) -> float:
    total = 0.0
    for index in range(len(points) - 1):
        x1, y1 = points[index][:2]
        x2, y2 = points[index + 1][:2]
        total += ((float(x2) - float(x1)) ** 2 + (float(y2) - float(y1)) ** 2) ** 0.5
    return total


def diagnose(feature: dict[str, Any], collection: dict[str, Any]) -> dict[str, Any]:
    props = feature.get("properties") or {}
    geom = feature.get("geometry") or {}
    coordinates = geom.get("coordinates") or []
    outer = coordinates[0] if geom.get("type") == "Polygon" and coordinates else []
    raw_ids = props.get("raw_fragment_ids_sample") or []
    return {
        "fid": props.get("FID"),
        "feature_id": feature.get("id"),
        "geometry_type": geom.get("type"),
        "bbox": props.get("bbox_page_pt") or geometry_bbox(geom),
        "area": round(geometry_area(geom), 3),
        "perimeter": round(ring_perimeter(outer), 3) if outer else 0,
        "holes": max(0, len(coordinates) - 1) if geom.get("type") == "Polygon" else 0,
        "source_merged_group": props.get("merged_group_id"),
        "source_fragment_ids_sample": raw_ids[:12],
        "source_vector_style": {
            "source_fill_hex": props.get("source_fill_hex") or props.get("source_style_hex"),
            "source_stroke_hex": props.get("source_stroke_hex"),
            "source_fill_opacity": props.get("source_fill_opacity"),
            "source_stroke_opacity": props.get("source_stroke_opacity"),
            "source_style_group_id": props.get("source_style_group_id"),
        },
        "matched_legend_item_id": props.get("matched_legend_item_id"),
        "matched_vector_def_id": props.get("matched_vector_def_id"),
        "proposed_class": props.get("proposed_CLASS"),
        "proposed_type": props.get("proposed_TYPE"),
        "display_color": {
            "display_fill_hex": props.get("display_fill_hex"),
            "display_stroke_hex": props.get("display_stroke_hex"),
            "display_color_source": props.get("display_color_source"),
        },
        "artifact_flags": props.get("artifact_flags"),
        "geometry_decision": props.get("geometry_decision"),
        "geometry_decision_reason": props.get("geometry_decision_reason"),
        "review_required": props.get("review_required"),
        "export_eligible": props.get("export_eligible"),
        "artifact_component_count": props.get("artifact_component_count"),
        "component_count_before": props.get("component_count_before"),
        "component_count_after": props.get("component_count_after"),
        "disconnected_selected_border_component_count": props.get("disconnected_selected_border_component_count"),
        "island_count": props.get("island_count"),
        "spike_score": props.get("spike_score"),
        "spike_count": 1 if (props.get("spike_score") or 0) >= 0.55 else 0,
        "needle_count": props.get("needle_count"),
        "sliver_component_count": props.get("sliver_component_count"),
        "thin_corridor_count": props.get("thin_corridor_count"),
        "hole_metrics": {
            "triangular_void_count": props.get("triangular_void_count"),
            "small_void_count": props.get("small_void_count"),
            "void_area_ratio": props.get("void_area_ratio"),
            "void_matches_original_plan": props.get("void_matches_original_plan"),
            "void_requires_review_count": props.get("void_requires_review_count"),
        },
        "nearest_text_or_legend_evidence": {
            "source_text_nearby": props.get("source_text_nearby"),
            "classification_reason": props.get("classification_reason"),
        },
        "export_blocking_reason": props.get("export_blocking_reason"),
        "trust_decision": props.get("artifact_trust_state"),
        "geometry_cleanup": {
            "cleanup_applied": props.get("cleanup_applied"),
            "geometry_cleanup_algorithm": props.get("geometry_cleanup_algorithm"),
            "geometry_cleanup_tolerance": props.get("geometry_cleanup_tolerance"),
            "geometry_cleanup_reason": props.get("geometry_cleanup_reason"),
            "cleanup_before_summary": props.get("cleanup_before_summary"),
            "cleanup_after_summary": props.get("cleanup_after_summary"),
            "cleaned_candidate_available": props.get("cleaned_candidate_available"),
            "cleaned_candidate_reason": props.get("cleaned_candidate_reason"),
            "cleaned_candidate_metadata": (props.get("cleaned_candidate_geometry") or {}).get("review_candidate_metadata") if isinstance(props.get("cleaned_candidate_geometry"), dict) else None,
        },
        "collection_artifact_summary": collection.get("artifact_diagnostics"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fid", type=int, default=329)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "docs" / "kamenice_fid329_diagnostic.json")
    args = parser.parse_args()
    pdf = find_pdf()
    collection = extract_vector_candidates(pdf, source_url=f"diagnose:{pdf.name}")
    feature = next(
        (row for row in collection.get("features", []) if (row.get("properties") or {}).get("FID") == args.fid),
        None,
    )
    if feature is None:
        args.out.write_text(
            json.dumps(
                {
                    "status": "not_found",
                    "requested_fid": args.fid,
                    "feature_count": collection.get("feature_count"),
                    "reason": "FID is not stable in the current merged output",
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(args.out.read_text(encoding="utf-8"))
        sys.exit(1)
    report = {"status": "found", "pdf": str(pdf), **diagnose(feature, collection)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
