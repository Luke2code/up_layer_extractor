from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.algorithms import extract_vector_candidates


DEFAULT_OUTPUT_JSON = REPO_ROOT / "docs" / "pdf_validation_corpus.json"
DEFAULT_OUTPUT_CSV = REPO_ROOT / "docs" / "pdf_validation_corpus.csv"
DEFAULT_PDFS = [
    Path("/mnt/c/demo/Input/UP__MNICHOVICE__538493__UZ_1__HLV.PDF"),
    Path("/mnt/c/demo/Input/UP__SVETICE___A_PV__538841___UZ_1_HLV.pdf"),
    Path("/mnt/c/demo/Input/UP_538728_RICANY_HLV.pdf"),
    Path("/mnt/c/Users/Me/Downloads/kamenice zcu.pdf"),
    Path("/mnt/c/Users/Me/Downloads/bykev_2-výkres základního členění.pdf"),
    Path("/mnt/c/Users/Me/Downloads/bykev_3-hlavní výkres.pdf"),
    Path("/mnt/c/Users/Me/Downloads/A_PV___KAMENICE___538299___UZ_9_15___HLV.pdf"),
    Path("/mnt/c/stg_db/data/up_import/A_PV/MUKAROV___538523/UZ_2/A_PV___MUKAROV___538523___UZ_2___HLV.pdf"),
    Path("/mnt/c/stg_db/data/up_import/A_PV/STRUHAROV___538825/UZ_2/A_PV___STRUHAROV___538825___UZ_2___ZCU.pdf"),
]


def validate_one(path: Path) -> dict[str, Any]:
    start = time.perf_counter()
    if not path.exists():
        return {
            "filename": str(path),
            "status": "missing",
            "notes": "file not found",
        }
    try:
        collection = extract_vector_candidates(path, source_url=f"validation:{path.name}")
        runtime_ms = round((time.perf_counter() - start) * 1000)
        detection = collection.get("source_detection") or {}
        diagnostics = collection.get("diagnostics") or {}
        return {
            "filename": path.name,
            "path": str(path),
            "source_fingerprint": collection.get("source_fingerprint"),
            "source_type": collection.get("source_type") or detection.get("source_type"),
            "page_count": collection.get("page_count") or detection.get("page_count"),
            "vector_drawing_count": diagnostics.get("drawing_count") or detection.get("drawing_count"),
            "text_span_count": detection.get("text_span_count"),
            "vector_feature_count": len(collection.get("features") or []),
            "raw_fragment_count": collection.get("raw_fragment_count"),
            "primary_extraction_mode": collection.get("primary_extraction_mode"),
            "raw_features_are_debug_only": collection.get("raw_features_are_debug_only"),
            "tessellated_fill_detected": (collection.get("tessellation_metrics") or {}).get("tessellated_fill_detected"),
            "merged_group_count": (collection.get("merge_stats") or {}).get("merged_group_count"),
            "vector_def_count": collection.get("vector_def_count", 0),
            "text_def_count": collection.get("text_def_count", 0),
            "legend_crop_count": collection.get("legend_crop_count", 0),
            "inscope_classification_proposal_count": len([row for row in collection.get("classification_proposals") or [] if row.get("is_inscope_bydleni_related")]),
            "requires_review_count": len([row for row in collection.get("classification_proposals") or [] if row.get("requires_review")]),
            "geometry_error_count": collection.get("geometry_error_count_total", len(collection.get("geometry_error_candidates") or [])),
            "structured_error_count": len(collection.get("structured_errors") or []),
            "runtime_ms": runtime_ms,
            "status": "passed" if collection.get("features") else collection.get("classification_status", "diagnostic_only"),
            "notes": collection.get("warning"),
        }
    except Exception as exc:  # pragma: no cover - exercised by operator corpus runs.
        runtime_ms = round((time.perf_counter() - start) * 1000)
        return {
            "filename": path.name,
            "path": str(path),
            "runtime_ms": runtime_ms,
            "status": "extraction_error",
            "notes": f"{type(exc).__name__}: {exc}",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate UP layer extraction against a PDF corpus.")
    parser.add_argument("pdfs", nargs="*", help="PDF paths. Defaults to the known user-provided corpus when omitted.")
    parser.add_argument("--json-out", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--csv-out", default=str(DEFAULT_OUTPUT_CSV))
    args = parser.parse_args()

    paths = [Path(value) for value in args.pdfs] if args.pdfs else DEFAULT_PDFS
    rows = [validate_one(path) for path in paths]

    json_out = Path(args.json_out)
    csv_out = Path(args.csv_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    headers = sorted({key for row in rows for key in row})
    with csv_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    print(f"validated {len(rows)} PDFs")
    print(f"json={json_out}")
    print(f"csv={csv_out}")
    for row in rows:
        print(f"{row.get('status')}: {row.get('filename')} features={row.get('vector_feature_count', 0)} errors={row.get('structured_error_count', 0)}")


if __name__ == "__main__":
    main()
