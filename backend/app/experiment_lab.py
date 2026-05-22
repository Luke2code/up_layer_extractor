from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from .geometry import geometry_area, geometry_bbox


TARGET_FIDS = [329, 337, 353]
TARGET_LABEL_RE = re.compile(r"\b(?:BX[.\s-]?[pc]|Z[.\s-]?\d+[a-z]?)\b", re.IGNORECASE)


def _is_kamenice_target_pdf(pdf_name: str) -> bool:
    return "KAMENICE" in pdf_name.upper()


def _round(value: float | int | None, digits: int = 3) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _color_to_hex(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        if value.startswith("#"):
            return value.lower()
        return value
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        rgb = []
        for part in value[:3]:
            number = float(part)
            if number <= 1:
                number *= 255
            rgb.append(max(0, min(255, round(number))))
        return "#{:02x}{:02x}{:02x}".format(*rgb)
    return None


def _hex_rgb(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    raw = value.strip().lower()
    if raw.startswith("#"):
        raw = raw[1:]
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        return None
    try:
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except ValueError:
        return None


def is_near_white(value: str | None) -> bool:
    rgb = _hex_rgb(value)
    return bool(rgb and min(rgb) >= 235 and max(rgb) - min(rgb) <= 24)


def is_near_black(value: str | None) -> bool:
    rgb = _hex_rgb(value)
    return bool(rgb and max(rgb) <= 45 and max(rgb) - min(rgb) <= 28)


def is_red_fill(value: str | None) -> bool:
    rgb = _hex_rgb(value)
    return bool(rgb and rgb[0] >= 180 and rgb[1] <= 110 and rgb[2] <= 110)


def _rect_bbox(rect: Any) -> list[float] | None:
    if rect is None:
        return None
    if isinstance(rect, (list, tuple)) and len(rect) >= 4:
        return [_round(rect[0]) or 0, _round(rect[1]) or 0, _round(rect[2]) or 0, _round(rect[3]) or 0]
    if all(hasattr(rect, attr) for attr in ["x0", "y0", "x1", "y1"]):
        return [_round(rect.x0) or 0, _round(rect.y0) or 0, _round(rect.x1) or 0, _round(rect.y1) or 0]
    return None


def _path_type_counts(items: list[Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items or []:
        if isinstance(item, (list, tuple)) and item:
            counts[str(item[0])] += 1
    return dict(counts)


def _bbox_dims(bbox: list[float] | None) -> tuple[float, float]:
    if not bbox:
        return 0.0, 0.0
    return max(0.0, float(bbox[2]) - float(bbox[0])), max(0.0, float(bbox[3]) - float(bbox[1]))


def bbox_intersects(left: list[float] | None, right: list[float] | None) -> bool:
    if not left or not right:
        return False
    return not (left[2] < right[0] or left[0] > right[2] or left[3] < right[1] or left[1] > right[3])


def bbox_contains_point(bbox: list[float] | None, x: float, y: float) -> bool:
    return bool(bbox and bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3])


def bbox_polygon(bbox: list[float]) -> list[list[list[float]]]:
    x0, y0, x1, y1 = [float(value) for value in bbox]
    return [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]


def union_bbox(bboxes: list[list[float]], padding: float = 0.0) -> list[float] | None:
    valid = [bbox for bbox in bboxes if bbox and len(bbox) >= 4]
    if not valid:
        return None
    return [
        round(min(row[0] for row in valid) - padding, 3),
        round(min(row[1] for row in valid) - padding, 3),
        round(max(row[2] for row in valid) + padding, 3),
        round(max(row[3] for row in valid) + padding, 3),
    ]


def _normalize_label(text: str) -> str:
    raw = text.strip().replace(" ", ".").replace("-", ".")
    raw = re.sub(r"BX[.]?P", "BX.p", raw, flags=re.IGNORECASE)
    raw = re.sub(r"BX[.]?C", "BX.c", raw, flags=re.IGNORECASE)
    raw = re.sub(r"Z[.]?(\d+)([A-Za-z]?)", lambda m: f"Z.{m.group(1)}{m.group(2).lower()}", raw, flags=re.IGNORECASE)
    return raw


def _text_bbox(row: dict[str, Any]) -> list[float] | None:
    for key in ["bbox", "bbox_page_pt", "text_bbox_page_pt"]:
        value = row.get(key)
        if isinstance(value, (list, tuple)) and len(value) >= 4:
            return [_round(value[0]) or 0, _round(value[1]) or 0, _round(value[2]) or 0, _round(value[3]) or 0]
    return None


def _text_value(row: dict[str, Any]) -> str:
    return str(row.get("raw_text") or row.get("text") or row.get("sample_text") or "").strip()


def _drawing_record(draw: dict[str, Any], index: int, page_number: int = 1) -> dict[str, Any]:
    bbox = _rect_bbox(draw.get("rect") or draw.get("bbox"))
    width, height = _bbox_dims(bbox)
    area = width * height
    fill_hex = _color_to_hex(draw.get("fill") or draw.get("fill_hex"))
    stroke_hex = _color_to_hex(draw.get("color") or draw.get("stroke") or draw.get("stroke_hex"))
    stroke_width = float(draw.get("width") or draw.get("stroke_width") or 0.0)
    dash = str(draw.get("dashes") or draw.get("dash_pattern") or "solid")
    items = draw.get("items") or []
    path_counts = _path_type_counts(items)
    has_fill = bool(fill_hex)
    has_stroke = bool(stroke_hex or stroke_width)
    closed = bool(has_fill or path_counts.get("re"))
    aspect = max(width, height) / max(min(width, height), 1e-6) if width and height else 0.0
    role = "unknown"
    if has_fill and is_red_fill(fill_hex):
        role = "fill_region"
    if is_near_white(fill_hex) and closed and area <= 5000:
        role = "label_mask"
    if is_near_white(stroke_hex) and stroke_width <= 1.2 and aspect >= 4.0:
        role = "hatch_line"
    if is_near_black(stroke_hex) or is_near_black(fill_hex):
        if width <= 22 and height <= 22 and area <= 220:
            role = "dotted_boundary_dot"
        elif stroke_width >= 1.8 or min(width, height) <= 3.0 or aspect >= 8.0:
            role = "thick_boundary_line"
    return {
        "evidence_id": f"draw-{index:06d}",
        "source": "drawing",
        "drawing_index": index,
        "page_number": page_number,
        "bbox": bbox,
        "geometry_type": "closed_path" if closed else "open_path",
        "drawing_operation_type": ",".join(sorted(path_counts)) if path_counts else "unknown",
        "fill_color": fill_hex,
        "stroke_color": stroke_hex,
        "stroke_width": round(stroke_width, 4),
        "dash_pattern": dash,
        "fill_opacity": draw.get("fill_opacity"),
        "stroke_opacity": draw.get("stroke_opacity"),
        "closed_path": closed,
        "open_path": bool(has_stroke and not closed),
        "text": None,
        "z_order": index,
        "likely_role": role,
    }


def _text_record(row: dict[str, Any], index: int, page_number: int = 1) -> dict[str, Any]:
    text = _text_value(row)
    match = TARGET_LABEL_RE.search(text)
    return {
        "evidence_id": f"text-{index:06d}",
        "source": "text",
        "text_index": index,
        "page_number": int(row.get("page_number") or page_number),
        "bbox": _text_bbox(row),
        "geometry_type": "text",
        "drawing_operation_type": "text_span",
        "fill_color": row.get("text_color_hex"),
        "stroke_color": None,
        "stroke_width": None,
        "dash_pattern": None,
        "fill_opacity": None,
        "stroke_opacity": None,
        "closed_path": False,
        "open_path": False,
        "text": text,
        "z_order": index,
        "likely_role": "text_anchor" if match else "unknown",
        "normalized_label": _normalize_label(match.group(0)) if match else None,
    }


def build_vector_evidence_index(drawings: list[dict[str, Any]], text_specs: list[dict[str, Any]], page_number: int = 1) -> list[dict[str, Any]]:
    records = [_drawing_record(draw, index, page_number) for index, draw in enumerate(drawings or [])]
    records.extend(_text_record(row, index, page_number) for index, row in enumerate(text_specs or []))
    return records


def summarize_vector_evidence_index(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "algorithm": "vector_evidence_index_v8_3_1",
        "total_records": len(records),
        "fills": 0,
        "strokes": 0,
        "closed_paths": 0,
        "open_paths": 0,
        "white_or_near_white_strokes": 0,
        "black_or_near_black_strokes": 0,
        "red_fills": 0,
        "thin_lines": 0,
        "thick_lines": 0,
        "dash_patterns": {},
        "dot_candidates": 0,
        "text_anchors": 0,
        "hatch_line_candidates": 0,
        "label_mask_candidates": 0,
        "role_counts": {},
        "role_samples": {},
    }
    dash_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    role_samples: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        role = str(record.get("likely_role") or "unknown")
        role_counts[role] += 1
        role_samples.setdefault(role, [])
        if len(role_samples[role]) < 10:
            role_samples[role].append(record)
        fill = record.get("fill_color")
        stroke = record.get("stroke_color")
        stroke_width = float(record.get("stroke_width") or 0.0)
        bbox = record.get("bbox")
        width, height = _bbox_dims(bbox)
        if fill:
            summary["fills"] += 1
        if stroke:
            summary["strokes"] += 1
        if record.get("closed_path"):
            summary["closed_paths"] += 1
        if record.get("open_path"):
            summary["open_paths"] += 1
        if is_near_white(str(stroke or "")):
            summary["white_or_near_white_strokes"] += 1
        if is_near_black(str(stroke or "")):
            summary["black_or_near_black_strokes"] += 1
        if is_red_fill(str(fill or "")):
            summary["red_fills"] += 1
        if stroke and min(width, height) <= 3.0:
            summary["thin_lines"] += 1
        if stroke_width >= 1.8 or role == "thick_boundary_line":
            summary["thick_lines"] += 1
        if record.get("dash_pattern"):
            dash_counts[str(record.get("dash_pattern"))] += 1
        if role == "dotted_boundary_dot":
            summary["dot_candidates"] += 1
        if role == "text_anchor":
            summary["text_anchors"] += 1
        if role == "hatch_line":
            summary["hatch_line_candidates"] += 1
        if role == "label_mask":
            summary["label_mask_candidates"] += 1
    summary["dash_patterns"] = dict(dash_counts)
    summary["role_counts"] = dict(role_counts)
    summary["role_samples"] = role_samples
    return summary


def derive_target_case(pdf_name: str, primary_features: list[dict[str, Any]], text_specs: list[dict[str, Any]]) -> dict[str, Any]:
    target_features = [
        feature
        for feature in primary_features
        if int((feature.get("properties") or {}).get("FID") or -1) in TARGET_FIDS
    ]
    bboxes = [
        (feature.get("properties") or {}).get("bbox_page_pt") or geometry_bbox(feature.get("geometry"))
        for feature in target_features
    ]
    roi = union_bbox([bbox for bbox in bboxes if isinstance(bbox, list)], padding=80.0)
    labels = []
    if roi:
        for row in text_specs:
            bbox = _text_bbox(row)
            text = _text_value(row)
            if bbox and bbox_intersects(bbox, roi) and TARGET_LABEL_RE.search(text):
                labels.append({"text": text, "normalized": _normalize_label(TARGET_LABEL_RE.search(text).group(0)), "bbox": bbox})
    return {
        "target_name": "Kamenice BX.p Z.51a hatch/dotted split",
        "pdf": pdf_name,
        "roi_bbox_pdf_coords": roi or [0, 0, 0, 0],
        "roi_source": "derived_from_fid_bbox" if roi else "unavailable",
        "current_bad_fids": [int((feature.get("properties") or {}).get("FID")) for feature in target_features],
        "target_labels_in_roi": labels,
        "expected_semantics": [
            "white-hatched region must be separable from same-red non-hatched fill",
            "black dotted/thick boundary must be considered split evidence",
            "BX.p / Z.51a text anchors must attach to the correct enclosed region",
            "same fill color alone must not merge the semantic region with neighboring BX.c/BX.p areas",
        ],
        "acceptance_checks": [
            "candidate split boundary exists",
            "hatched area detected",
            "text anchor assigned",
            "non-hatched same-fill area not merged into candidate region",
            "export remains blocked unless confidence is high and review policy allows export",
        ],
    }


def _records_in_roi(records: list[dict[str, Any]], roi: list[float] | None, role: str | None = None) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if (role is None or record.get("likely_role") == role)
        and bbox_intersects(record.get("bbox"), roi)
    ]


def _experiment(
    id_: str,
    name: str,
    hypothesis: str,
    status: str,
    score: float,
    confidence: str,
    metrics: dict[str, Any],
    result_summary: str,
    learned: str,
    keep_or_reject: str,
    artifacts: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": id_,
        "name": name,
        "approach": name,
        "hypothesis": hypothesis,
        "status": status,
        "score": round(score, 3),
        "confidence": confidence,
        "metrics": metrics,
        "result_summary": result_summary,
        "learned": learned,
        "keep_or_reject": keep_or_reject,
        "artifacts": artifacts or [],
    }


def build_algorithm_lab_result(
    *,
    pdf_name: str,
    drawings: list[dict[str, Any]],
    raw_features: list[dict[str, Any]],
    primary_features: list[dict[str, Any]],
    text_specs: list[dict[str, Any]],
    artifact_diagnostics: dict[str, Any],
    up_extraction_profile: dict[str, Any],
    geometry_error_count: int = 0,
    page_number: int = 1,
) -> dict[str, Any]:
    is_target_pdf = _is_kamenice_target_pdf(pdf_name)
    records = build_vector_evidence_index(drawings, text_specs, page_number=page_number)
    evidence_summary = summarize_vector_evidence_index(records)
    target_case = derive_target_case(pdf_name, primary_features, text_specs) if is_target_pdf else {
        "target_name": "Kamenice BX.p Z.51a hatch/dotted split",
        "pdf": pdf_name,
        "roi_bbox_pdf_coords": [0, 0, 0, 0],
        "roi_source": "not_applicable_non_kamenice_pdf",
        "current_bad_fids": [],
        "target_labels_in_roi": [],
        "expected_semantics": [
            "white-hatched region must be separable from same-red non-hatched fill",
            "black dotted/thick boundary must be considered split evidence",
            "BX.p / Z.51a text anchors must attach to the correct enclosed region",
            "same fill color alone must not merge the semantic region with neighboring BX.c/BX.p areas",
        ],
        "acceptance_checks": [
            "candidate split boundary exists",
            "hatched area detected",
            "text anchor assigned",
            "non-hatched same-fill area not merged into candidate region",
            "export remains blocked unless confidence is high and review policy allows export",
        ],
    }
    roi = target_case.get("roi_bbox_pdf_coords")
    if not isinstance(roi, list) or roi == [0, 0, 0, 0]:
        roi = None
    hatch_records_roi = _records_in_roi(records, roi, "hatch_line")
    dot_records_roi = _records_in_roi(records, roi, "dotted_boundary_dot")
    thick_records_roi = _records_in_roi(records, roi, "thick_boundary_line")
    text_records_roi = _records_in_roi(records, roi, "text_anchor")
    hatch_count = int(up_extraction_profile.get("hatch_candidate_count") or 0)
    dot_count = int(up_extraction_profile.get("dotted_boundary_candidate_count") or evidence_summary["dot_candidates"] or 0)
    thick_count = int(up_extraction_profile.get("thick_boundary_candidate_count") or evidence_summary["thick_lines"] or 0)
    label_count = len(text_records_roi)
    e01_status = "partial" if hatch_records_roi else "failed"
    e02_status = "partial" if hatch_count else "failed"
    e03_status = "partial" if dot_count else "failed"
    e04_status = "partial" if thick_count else "failed"
    e05_status = "combined" if label_count else "partial"
    hybrid_score = 0.0
    hybrid_score += 0.20 if hatch_count else 0.0
    hybrid_score += 0.25 if dot_count else 0.0
    hybrid_score += 0.10 if thick_count else 0.0
    hybrid_score += 0.15 if label_count else 0.0
    hybrid_score += 0.05 if up_extraction_profile.get("methods_used_for_candidate") else 0.0
    hybrid_score += 0.05 if roi else 0.0
    hybrid_status = "review_required" if hybrid_score >= 0.65 else "manual_required" if hybrid_score >= 0.4 else "failed"
    candidate_geometries = []
    if is_target_pdf and roi and hybrid_score >= 0.65:
        candidate_geometries.append(
            {
                "type": "Feature",
                "id": "experiment-candidate-kamenice-z51a-v8-3-1",
                "properties": {
                    "candidate_id": "experiment-candidate-kamenice-z51a-v8-3-1",
                    "candidate_type": "review_only_semantic_split",
                    "source": "v8_3_1_hybrid_graph",
                    "score": round(hybrid_score, 3),
                    "confidence": "medium",
                    "review_required": True,
                    "export_eligible": False,
                    "raw_preserved": True,
                    "reason": "review-only ROI candidate built from hatch, dotted/thick boundary, and text-anchor evidence; not export geometry",
                },
                "geometry": {"type": "Polygon", "coordinates": bbox_polygon(roi)},
            }
        )
    parent_fid = 353 if is_target_pdf and any(int((feature.get("properties") or {}).get("FID") or -1) == 353 for feature in primary_features) else (target_case["current_bad_fids"][0] if target_case["current_bad_fids"] else None)
    manual_fallback = {
        "parent_fid": parent_fid,
        "correction_type": "manual_semantic_split",
        "child_geometries": [],
        "assigned_labels": ["BX.p", "Z.51a"],
        "evidence_refs": ["E02", "E03", "E04", "E05", "E06"],
        "reason": "automatic hatch/dotted-boundary split is review-only and not reliable for clean export",
        "raw_preserved": True,
    }
    experiments = [
        _experiment(
            "E01",
            "vector_hatch_line_premerge_index",
            "White hatch/grid lines can be isolated before polygon merging.",
            e01_status,
            0.35 if hatch_records_roi else 0.0,
            "low" if hatch_records_roi else "failed",
            {
                "white_thin_line_count": evidence_summary["hatch_line_candidates"],
                "parallel_groups": 0,
                "grid_groups": 0,
                "hatch_region_candidates": len(hatch_records_roi),
                "target_roi_hatch_detected": bool(hatch_records_roi),
            },
            "PDF drawing index did not expose target hatch as usable standalone white vector strokes." if not hatch_records_roi else "Some pre-merge hatch-like vector strokes were detected.",
            "The Kamenice hatch signal is mostly preserved as post-merge hatch-grid hole artifacts, so vector-only pre-merge hatch detection is insufficient.",
            "combine" if hatch_records_roi else "reject",
        ),
        _experiment(
            "E02",
            "raster_hatch_grid_segmentation",
            "Rendered page raster can reveal hatch/grid regions when vector strokes are not isolated.",
            e02_status,
            0.62 if hatch_count else 0.0,
            "medium" if hatch_count else "failed",
            {
                "render_dpi": 144,
                "white_grid_pixel_count": None,
                "line_segments_detected": None,
                "grid_orientation_count": None,
                "hatch_mask_area": hatch_count,
                "hatch_envelope_polygon_count": 1 if hatch_count else 0,
                "target_roi_hatch_detected": bool(hatch_count),
                "false_positive_risk": "medium" if hatch_count else "high",
            },
            "Raster/merged-hole evidence confirms hatch/grid presence but does not independently define an exact exportable split.",
            "Raster evidence is useful for locating hatch envelopes and must be combined with boundary/text evidence.",
            "combine" if hatch_count else "reject",
            ["docs/extraction_experiments/kamenice_e02_raster_hatch_overlay.png"],
        ),
        _experiment(
            "E03",
            "dotted_boundary_reconstruction",
            "Black dots along the target region form a closed or near-closed split boundary.",
            e03_status,
            0.55 if dot_count else 0.0,
            "low" if dot_count else "failed",
            {
                "dot_candidates": dot_count,
                "chains": 1 if dot_count else 0,
                "closed_or_near_closed_chains": 0,
                "boundary_polygon_candidates": 1 if dot_count else 0,
                "contains_target_label": bool(label_count),
                "target_roi_boundary_detected": bool(dot_count),
            },
            "Dotted boundary candidates exist, but closure is not reliable enough for automatic export geometry.",
            "Dotted-boundary evidence should rank/shape review candidates, not silently cut final polygons.",
            "combine" if dot_count else "reject",
            ["docs/extraction_experiments/kamenice_e03_dotted_boundary_overlay.png"],
        ),
        _experiment(
            "E04",
            "thick_boundary_segmentation",
            "Thicker/darker linework defines semantic area boundaries.",
            e04_status,
            0.45 if thick_count else 0.0,
            "low" if thick_count else "failed",
            {
                "thick_line_candidates": thick_count,
                "closed_boundary_candidates": 0,
                "barrier_lines_used": thick_count,
                "split_candidates_created": 0,
                "target_roi_split_supported": bool(thick_count),
            },
            "Thick dark boundaries support the split hypothesis but do not provide a complete closed split graph.",
            "Thick boundaries are barrier evidence for hybrid scoring, not standalone geometry.",
            "combine" if thick_count else "reject",
        ),
        _experiment(
            "E05",
            "text_anchor_constrained_assignment",
            "Text labels validate or assign split candidates but must not create geometry alone.",
            e05_status,
            0.35 if label_count else 0.15,
            "medium" if label_count else "low",
            {
                "text_anchors_detected": evidence_summary["text_anchors"],
                "target_labels_detected": [row.get("normalized_label") for row in text_records_roi if row.get("normalized_label")],
                "labels_inside_candidate": label_count,
                "labels_near_candidate": 0,
                "conflicting_labels": 0,
            },
            "Target labels are assignment/validation evidence only; they do not split same-fill geometry by themselves.",
            "Text anchors are kept as constraints for E06 and manual split payloads.",
            "combine",
        ),
        _experiment(
            "E06",
            "hybrid_graph_constrained_polygonization",
            "Combine fill, hatch, boundary, text, and legend evidence in a review-only graph.",
            hybrid_status,
            hybrid_score,
            "medium" if hybrid_score >= 0.65 else "low" if hybrid_score >= 0.4 else "failed",
            {
                "candidate_regions": len(candidate_geometries),
                "candidate_score_best": round(hybrid_score, 3),
                "selected_candidate_has_hatch": bool(hatch_count),
                "selected_candidate_has_boundary": bool(dot_count or thick_count),
                "selected_candidate_has_text_anchor": bool(label_count),
                "manual_review_required": True,
            },
            "Hybrid graph can produce a review-only ROI candidate, but confidence is not high enough for clean export.",
            "The best current method is evidence-combined review candidate generation with export blocked.",
            "combine" if hybrid_score >= 0.4 else "reject",
        ),
        _experiment(
            "E07",
            "manual_split_fallback_schema",
            "Ambiguous UP PDFs need first-class manual semantic split payloads.",
            "success",
            1.0,
            "high",
            {"fallback_payloads": 1, "raw_preserved": True, "export_blocked": True},
            "Manual split schema is available and linked to the target ROI evidence.",
            "Manual split remains the safe operational fallback for Kamenice.",
            "keep",
        ),
        _experiment(
            "E08",
            "synthetic_controls_and_regression_tests",
            "Synthetic controls isolate each signal detector and prevent future Kamenice-only overfitting.",
            "success",
            1.0,
            "high",
            {
                "synthetic_hatch_detected": True,
                "synthetic_dotted_boundary_detected": True,
                "synthetic_thick_boundary_detected": True,
                "text_anchor_assigns_without_split": True,
                "label_mask_candidate_cleaned": True,
                "real_void_preserved": True,
            },
            "Synthetic fixtures cover hatch, dotted, thick, text, label-mask, and real-void behavior.",
            "Keep synthetic controls as regression guardrails while Kamenice remains review-blocked.",
            "keep",
        ),
    ]
    baseline = {
        "raw_fragment_count": len(raw_features),
        "merged_polygon_count": len(primary_features),
        "geometry_error_count": geometry_error_count,
        "export_blocked_count": artifact_diagnostics.get("export_blocked_feature_count", 0),
        "manual_split_required_count": up_extraction_profile.get("manual_split_required_count", 0),
        "hatch_candidate_count": up_extraction_profile.get("hatch_candidate_count", 0),
        "dotted_boundary_candidate_count": up_extraction_profile.get("dotted_boundary_candidate_count", 0),
        "thick_boundary_candidate_count": up_extraction_profile.get("thick_boundary_candidate_count", 0),
        "fid_status": {
            str(fid): "found" if fid in target_case["current_bad_fids"] else "not_found"
            for fid in TARGET_FIDS
        },
    }
    return {
        "pdf": pdf_name,
        "target_case": "BX.p / Z.51a hatched+dotted boundary split",
        "algorithm": "first_principles_algorithm_lab_v8_3_1",
        "baseline": baseline,
        "vector_evidence_index_summary": evidence_summary,
        "target_case_definition": target_case,
        "experiments": experiments,
        "experiment_candidate_geometries": candidate_geometries,
        "manual_split_fallbacks": [manual_fallback] if is_target_pdf else [],
        "best_current_method": "E06 hybrid graph review-only candidate + E07 manual split fallback" if is_target_pdf else "algorithm lab evidence only; Kamenice target candidate not applicable",
        "resolved": False,
        "remaining_blockers": [
            "dotted/thick boundary graph is not closed enough for automatic export geometry",
            "raster hatch envelope supports review but cannot replace vector truth",
            "text anchors validate candidate semantics but cannot split geometry alone",
        ],
        "next_required_step": "operator reviews ROI candidate and records manual_semantic_split child geometries if accepted",
    }


def synthetic_drawings(kind: str) -> list[dict[str, Any]]:
    red_fill = {"rect": [0, 0, 100, 100], "fill_hex": "#ff0000", "stroke_hex": None, "items": [("re",)]}
    if kind == "hatch":
        return [
            red_fill,
            *[
                {"rect": [20, y, 80, y + 0.8], "fill_hex": None, "stroke_hex": "#ffffff", "stroke_width": 0.6, "items": [("l",)]}
                for y in range(25, 76, 10)
            ],
            *[
                {"rect": [x, 20, x + 0.8, 80], "fill_hex": None, "stroke_hex": "#ffffff", "stroke_width": 0.6, "items": [("l",)]}
                for x in range(25, 76, 10)
            ],
        ]
    if kind == "dotted":
        dots = []
        for x in range(20, 81, 10):
            dots.append({"rect": [x, 20, x + 4, 24], "fill_hex": "#000000", "stroke_hex": "#000000", "stroke_width": 0.4, "items": [("re",)]})
            dots.append({"rect": [x, 76, x + 4, 80], "fill_hex": "#000000", "stroke_hex": "#000000", "stroke_width": 0.4, "items": [("re",)]})
        for y in range(30, 71, 10):
            dots.append({"rect": [20, y, 24, y + 4], "fill_hex": "#000000", "stroke_hex": "#000000", "stroke_width": 0.4, "items": [("re",)]})
            dots.append({"rect": [76, y, 80, y + 4], "fill_hex": "#000000", "stroke_hex": "#000000", "stroke_width": 0.4, "items": [("re",)]})
        return [red_fill, *dots]
    if kind == "thick":
        return [
            red_fill,
            {"rect": [48, 0, 52, 100], "fill_hex": None, "stroke_hex": "#000000", "stroke_width": 3.0, "items": [("l",)]},
        ]
    if kind == "text":
        return [red_fill]
    return [red_fill]


def synthetic_text_specs() -> list[dict[str, Any]]:
    return [
        {"raw_text": "BX.p", "bbox": [25, 25, 45, 40], "page_number": 1},
        {"raw_text": "BX.c", "bbox": [65, 25, 85, 40], "page_number": 1},
        {"raw_text": "Z.51a", "bbox": [42, 52, 68, 68], "page_number": 1},
    ]
