from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.algorithms import extract_vector_candidates
from scripts.run_kamenice_v8_3_experiments import OUT_DIR, find_pdf


REPORT = OUT_DIR / "kamenice_target_case_validation.json"


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def validate() -> dict[str, Any]:
    failures: list[str] = []
    pdf = find_pdf()
    collection = extract_vector_candidates(pdf, source_url=f"v8.3.1-target-validation:{pdf.name}")
    result = collection.get("algorithm_lab_result") or {}
    target = collection.get("target_case_v8_3") or result.get("target_case_definition") or {}
    experiments = collection.get("extraction_experiments") or []
    experiment_ids = {row.get("id") for row in experiments}
    candidate_geometries = collection.get("experiment_candidate_geometries") or []
    vector_summary = collection.get("vector_evidence_index_summary") or {}
    up_profile = collection.get("up_extraction_profile") or {}
    artifact = collection.get("artifact_diagnostics") or {}

    if target.get("roi_bbox_pdf_coords") in (None, [0, 0, 0, 0]):
        fail("target ROI was not identified reproducibly", failures)
    for fid in [329, 337, 353]:
        if fid not in (target.get("current_bad_fids") or []):
            fail(f"target FID {fid} is not reproducible", failures)
    for experiment_id in [f"E{index:02d}" for index in range(1, 9)]:
        if experiment_id not in experiment_ids:
            fail(f"experiment {experiment_id} is missing", failures)
    if not vector_summary:
        fail("vector evidence index summary is missing", failures)
    if int(vector_summary.get("dot_candidates") or 0) <= 0:
        fail("vector evidence index did not record dot candidates", failures)
    if int(up_profile.get("hatch_candidate_count") or 0) <= 0:
        fail("hatch/grid evidence is missing from extraction profile", failures)
    if up_profile.get("export_status") != "blocked":
        fail("target case is not export-blocked", failures)
    if int(artifact.get("export_blocked_feature_count") or 0) <= 0:
        fail("artifact diagnostics do not report export-blocked features", failures)
    for candidate in candidate_geometries:
        props = candidate.get("properties") or {}
        if props.get("export_eligible"):
            fail("experiment candidate is incorrectly export-eligible", failures)
        if not props.get("raw_preserved"):
            fail("experiment candidate does not state raw_preserved", failures)
    if not candidate_geometries:
        fail("no review-only experiment candidate geometry was emitted", failures)

    artifact_paths = [
        OUT_DIR / "KAMENICE_HLV_V8_3_EXPERIMENT_LEDGER.md",
        OUT_DIR / "kamenice_v8_3_experiment_results.json",
        OUT_DIR / "kamenice_target_case_v8_3.json",
        OUT_DIR / "kamenice_vector_evidence_index_summary.json",
        OUT_DIR / "kamenice_e02_raster_hatch_overlay.png",
        OUT_DIR / "kamenice_e02_raster_hatch_diagnostic.json",
        OUT_DIR / "kamenice_e03_dotted_boundary_overlay.png",
        OUT_DIR / "kamenice_e03_dotted_boundary_diagnostic.json",
    ]
    missing = [str(path) for path in artifact_paths if not path.exists() or path.stat().st_size <= 0]
    if missing:
        fail("required experiment artifacts are missing: " + ", ".join(missing), failures)

    return {
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "pdf": str(pdf),
        "target": target,
        "experiment_ids": sorted(experiment_ids),
        "candidate_count": len(candidate_geometries),
        "candidate_review_only": all(not ((row.get("properties") or {}).get("export_eligible")) for row in candidate_geometries),
        "export_status": up_profile.get("export_status"),
        "manual_split_required_count": up_profile.get("manual_split_required_count"),
        "hatch_candidate_count": up_profile.get("hatch_candidate_count"),
        "dotted_boundary_candidate_count": up_profile.get("dotted_boundary_candidate_count"),
        "vector_dot_candidates": vector_summary.get("dot_candidates"),
        "artifacts": [str(path) for path in artifact_paths],
    }


def main() -> None:
    result = validate()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "passed":
        sys.exit(1)


if __name__ == "__main__":
    main()
