from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import statistics
import time
import traceback
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .geometry import geometry_area, geometry_bbox

try:  # Optional at import time; required for tessellated vector merging.
    from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
    from shapely.ops import unary_union
    from shapely.validation import make_valid
except Exception:  # pragma: no cover - dependency availability is validated in operator runs.
    GeometryCollection = MultiPolygon = Polygon = None  # type: ignore[assignment]
    unary_union = None  # type: ignore[assignment]
    make_valid = None  # type: ignore[assignment]


TARGET_CODE_CLASSES = {
    "B": "BYDLENI",
    "BI": "BYDLENI",
    "BV": "BYDLENI",
    "BH": "BYDLENI",
    "BU": "BYDLENI",
    "BX.c": "BYDLENI",
    "BX.p": "BYDLENI",
    "BX.r": "BYDLENI",
    "R": "REKREACE",
    "RI": "REKREACE",
    "RX": "REKREACE",
    "S": "SMISENE_OBYTNE",
    "SO": "SMISENE_OBYTNE",
    "SV": "SMISENE_OBYTNE",
    "SC": "SMISENE_OBYTNE",
    "SX": "SMISENE_OBYTNE",
}

TARGET_CODE_ALIASES = {
    "BXC": "BX.c",
    "BX.C": "BX.c",
    "BXP": "BX.p",
    "BX.P": "BX.p",
    "BXR": "BX.r",
    "BX.R": "BX.r",
}

TARGET_LABEL_PATTERNS = [
    (r"\bsm[ií][sš]en[eé]\s+(obytn[eé]|bydlen[ií])\b", "S", "SMISENE_OBYTNE"),
    (r"\bbydlen[ií]\b|\bobyt(n[eé]|n[yý])\b", "B", "BYDLENI"),
    (r"\brekreac(e|n[ií]|n[yý])\b", "R", "REKREACE"),
]

KNOWN_RZVP_LABELS = {
    "B": "BYDLENÍ",
    "BI": "BYDLENÍ INDIVIDUÁLNÍ",
    "BV": "BYDLENÍ VENKOVSKÉ",
    "BH": "BYDLENÍ HROMADNÉ",
    "BU": "BYDLENÍ VŠEOBECNÉ",
    "BX.c": "BYDLENÍ JINÉ - ČISTÉ",
    "BX.p": "BYDLENÍ JINÉ - PŘÍMĚSTSKÉ",
    "BX.r": "BYDLENÍ JINÉ - REKREAČNÍ",
    "R": "REKREACE",
    "RI": "REKREACE INDIVIDUÁLNÍ",
    "RX": "REKREACE JINÁ",
    "S": "SMÍŠENÉ OBYTNÉ",
    "SO": "SMÍŠENÉ OBYTNÉ OBECNÉ",
    "SV": "SMÍŠENÉ OBYTNÉ VENKOVSKÉ",
    "SC": "SMÍŠENÉ OBYTNÉ CENTRÁLNÍ",
    "SX": "SMÍŠENÉ OBYTNÉ JINÉ",
}

CLASS_DISPLAY_COLORS = {
    "BI": "#d9483f",
    "BV": "#ce6f58",
    "BH": "#c75c91",
    "BU": "#d85b52",
    "BX.c": "#b95672",
    "BX.p": "#b66b8a",
    "BX.r": "#a26192",
    "RI": "#86b37f",
    "RX": "#74a36d",
    "SV": "#d98989",
    "SC": "#cc7f9f",
    "SX": "#bb8fce",
    "UNMAPPED": "#9ca3af",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def file_fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collection_fingerprint(collection: dict[str, Any]) -> str:
    normalized = json.dumps(collection, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def run_ids(source_fingerprint: str) -> tuple[str, str]:
    run_id = f"run-{source_fingerprint[:12]}"
    collection_id = f"collection-{source_fingerprint[12:24]}"
    return run_id, collection_id


def rgb_to_hex(rgb: Any) -> str | None:
    if rgb is None:
        return None
    try:
        if isinstance(rgb, int):
            return f"#{rgb & 0xFFFFFF:06x}"
        r, g, b = rgb[:3]
        if max(r, g, b) <= 1:
            r, g, b = r * 255, g * 255, b * 255
        return "#%02x%02x%02x" % (round(r), round(g), round(b))
    except Exception:
        return None


def fold_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.casefold()


def normalized_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", fold_text(value)).strip()


def detect_target_code(value: str | None) -> str | None:
    if not value:
        return None
    upper = re.sub(r"[^A-Z0-9.]", "", unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").upper())
    compact = upper.replace(".", "")
    code = TARGET_CODE_ALIASES.get(upper) or TARGET_CODE_ALIASES.get(compact) or upper
    return code if code in TARGET_CODE_CLASSES else None


def detect_target_label(value: str | None) -> tuple[str | None, str | None]:
    folded = normalized_text(value)
    if not folded:
        return None, None
    for pattern, code, group in TARGET_LABEL_PATTERNS:
        if re.search(pattern, folded):
            return code, group
    return None, None


def label_quality_fields(raw: str | None, code: str | None) -> dict[str, Any]:
    text = (raw or "").strip()
    letters = sum(1 for ch in text if ch.isalpha())
    bad_chars = sum(1 for ch in text if ch in "%<>/\\\"^~{}[]" or unicodedata.category(ch).startswith("C"))
    total = max(len(text), 1)
    garbled = not text or letters < 3 or (bad_chars / total) >= 0.18
    decoded = re.sub(r"\s+", " ", text).strip() if text else None
    if not garbled:
        return {
            "label_text_raw": raw,
            "label_text_decoded": decoded,
            "label_text_display": decoded,
            "label_text_status": "ok",
            "label_text_confidence": 0.82,
            "label_text_source": "pdf_text",
        }
    if code and code in KNOWN_RZVP_LABELS:
        return {
            "label_text_raw": raw,
            "label_text_decoded": None,
            "label_text_display": KNOWN_RZVP_LABELS[code],
            "label_text_status": "agent_proposed",
            "label_text_confidence": 0.55,
            "label_text_source": "agent_proposal",
            "label_text_review_required": True,
            "label_text_reason": "PDF text layer label was empty or garbled; display label is a review-required RZVP code proposal.",
        }
    return {
        "label_text_raw": raw,
        "label_text_decoded": None,
        "label_text_display": "label unreadable - review",
        "label_text_status": "manual_required",
        "label_text_confidence": 0.0,
        "label_text_source": "manual",
        "label_text_review_required": True,
        "label_text_reason": "PDF text layer label was empty or garbled and no deterministic label could be assigned.",
    }


def parse_dash_pattern(raw: Any) -> tuple[list[float] | None, float | None, str | None]:
    if raw in (None, "", []):
        return [], 0.0, "solid"
    text = str(raw)
    array_match = re.search(r"\[([^\]]*)\]", text)
    if array_match is not None:
        dash_array = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", array_match.group(1))]
        suffix = text[array_match.end() :]
        phases = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", suffix)]
        dash_phase = phases[-1] if phases else 0.0
    else:
        numbers = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", text)]
        if not numbers:
            return [], 0.0, "solid"
        dash_array = numbers[:-1] if len(numbers) > 1 else numbers
        dash_phase = numbers[-1] if len(numbers) > 1 else 0.0
    if not dash_array or all(abs(value) <= 1e-9 for value in dash_array):
        return [], 0.0, "solid"
    normalized = ",".join(f"{value:g}" for value in dash_array)
    if dash_phase:
        normalized = f"{normalized};phase={dash_phase:g}"
    return dash_array, dash_phase, normalized


def path_item_type_counts(items: Iterable[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        if item:
            key = str(item[0])
            counts[key] = counts.get(key, 0) + 1
    return counts


def rect_bbox(rect: Any) -> list[float] | None:
    if not rect:
        return None
    try:
        return [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]
    except Exception:
        return None


def bbox_area(bbox: list[float] | None) -> float:
    if not bbox:
        return 0.0
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def text_span_count(page: Any) -> int:
    count = 0
    try:
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                count += len(line.get("spans", []))
    except Exception:
        return 0
    return count


def median_float(values: Iterable[float], default: float = 0.0) -> float:
    cleaned = [float(value) for value in values if value is not None]
    if not cleaned:
        return default
    return float(statistics.median(cleaned))


def bbox_center(bbox: list[float] | None) -> tuple[float, float] | None:
    if not bbox:
        return None
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def bbox_intersection_area(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right:
        return 0.0
    x0 = max(left[0], right[0])
    y0 = max(left[1], right[1])
    x1 = min(left[2], right[2])
    y1 = min(left[3], right[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def bbox_contains_point(bbox: list[float] | None, point: tuple[float, float] | None) -> bool:
    if not bbox or point is None:
        return False
    return bbox[0] <= point[0] <= bbox[2] and bbox[1] <= point[1] <= bbox[3]


def bbox_to_image_bbox(bbox: list[float] | None, transform: dict[str, float] | None) -> list[float] | None:
    if not bbox or not transform:
        return None
    scale_x = float(transform["page_to_image_scale_x"])
    scale_y = float(transform["page_to_image_scale_y"])
    offset_x = float(transform["page_to_image_offset_x"])
    offset_y = float(transform["page_to_image_offset_y"])
    return [
        round(bbox[0] * scale_x + offset_x, 3),
        round(bbox[1] * scale_y + offset_y, 3),
        round(bbox[2] * scale_x + offset_x, 3),
        round(bbox[3] * scale_y + offset_y, 3),
    ]


def page_to_image_transform(crop_bbox: list[float] | None, image_width: int | None, image_height: int | None) -> dict[str, float] | None:
    if not crop_bbox or not image_width or not image_height:
        return None
    width = max(crop_bbox[2] - crop_bbox[0], 1e-9)
    height = max(crop_bbox[3] - crop_bbox[1], 1e-9)
    scale_x = float(image_width) / width
    scale_y = float(image_height) / height
    return {
        "page_to_image_scale_x": scale_x,
        "page_to_image_scale_y": scale_y,
        "page_to_image_offset_x": -crop_bbox[0] * scale_x,
        "page_to_image_offset_y": -crop_bbox[1] * scale_y,
    }


def render_plan_page_snapshot(
    *,
    page: Any,
    collection_id: str,
    page_number: int,
    scale: float = 1.0,
) -> dict[str, Any]:
    page_width = float(page.rect.width)
    page_height = float(page.rect.height)
    try:
        fitz = __import__("fitz")
        repo_root = Path(__file__).resolve().parents[2]
        out_dir = repo_root / "docs" / "plan_snapshots"
        out_dir.mkdir(parents=True, exist_ok=True)
        artifact = out_dir / f"{collection_id}_page_{page_number:04d}.png"
        matrix = fitz.Matrix(scale, scale)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        pixmap.save(str(artifact))
        image_width = int(pixmap.width)
        image_height = int(pixmap.height)
        scale_x = image_width / max(page_width, 1e-9)
        scale_y = image_height / max(page_height, 1e-9)
        transform = {
            "page_width_pt": page_width,
            "page_height_pt": page_height,
            "image_width_px": image_width,
            "image_height_px": image_height,
            "page_to_image_scale_x": scale_x,
            "page_to_image_scale_y": scale_y,
            "page_to_image_offset_x": 0.0,
            "page_to_image_offset_y": 0.0,
            "image_to_page_scale_x": 1.0 / max(scale_x, 1e-9),
            "image_to_page_scale_y": 1.0 / max(scale_y, 1e-9),
            "image_to_page_offset_x": 0.0,
            "image_to_page_offset_y": 0.0,
            "page_coordinate_y_axis": "down",
        }
        return {
            "plan_snapshot_available": True,
            "plan_snapshot_artifact_path": str(artifact),
            "plan_snapshot_url": f"/artifacts/plan_snapshots/{artifact.name}",
            "plan_snapshot_source": "pdf_page_render",
            "plan_snapshot_scale": {"x": scale_x, "y": scale_y},
            "plan_snapshot_page_number": page_number,
            "plan_snapshot_transform": transform,
            "plan_snapshot_width_px": image_width,
            "plan_snapshot_height_px": image_height,
        }
    except Exception as exc:
        return {
            "plan_snapshot_available": False,
            "plan_snapshot_artifact_path": None,
            "plan_snapshot_url": None,
            "plan_snapshot_source": "unavailable",
            "plan_snapshot_scale": None,
            "plan_snapshot_page_number": page_number,
            "plan_snapshot_transform": None,
            "plan_snapshot_error": f"{type(exc).__name__}: {exc}",
        }


def feature_bbox(feature: dict[str, Any]) -> list[float] | None:
    props = feature.get("properties") or {}
    bbox = props.get("bbox_page_pt")
    if bbox:
        return [float(value) for value in bbox]
    geom_bbox = geometry_bbox(feature.get("geometry") or {})
    return [float(value) for value in geom_bbox] if geom_bbox else None


def feature_exterior_point_count(feature: dict[str, Any]) -> int:
    geom = feature.get("geometry") or {}
    coordinates = geom.get("coordinates") or []
    if geom.get("type") == "Polygon" and coordinates:
        return len(coordinates[0])
    if geom.get("type") == "MultiPolygon" and coordinates and coordinates[0]:
        return len(coordinates[0][0])
    return 0


def page_dimensions(collection: dict[str, Any], page: Any | None = None) -> tuple[float, float]:
    width = collection.get("page_width_pt")
    height = collection.get("page_height_pt")
    if (not width or not height) and page is not None:
        width = float(page.rect.width)
        height = float(page.rect.height)
    return float(width or 0.0), float(height or 0.0)


def derive_legend_bbox(
    *,
    text_specs: list[dict[str, Any]],
    page_width: float,
    page_height: float,
) -> dict[str, Any]:
    def clipped_bbox(values: list[float]) -> list[float] | None:
        if len(values) != 4:
            return None
        bbox = [
            max(0.0, min(page_width, float(values[0]))),
            max(0.0, min(page_height, float(values[1]))),
            max(0.0, min(page_width, float(values[2]))),
            max(0.0, min(page_height, float(values[3]))),
        ]
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            return None
        return [round(value, 3) for value in bbox]

    def candidate_record(
        *,
        candidate_id: str,
        strategy: str,
        bbox: list[float] | None,
        anchors: list[dict[str, Any]],
        base_score: float,
        signals: dict[str, Any],
    ) -> dict[str, Any]:
        clipped = clipped_bbox(bbox or [])
        target_codes = {
            row.get("matched_code_candidate")
            for row in text_specs
            if row.get("matched_code_candidate") and clipped and bbox_contains_point(clipped, bbox_center(row.get("bbox_page_pt")))
        }
        keyword_count = int(signals.get("keyword_text_count") or 0)
        class_code_count = len([code for code in target_codes if code])
        score = min(1.0, base_score + min(class_code_count, 8) * 0.035 + min(keyword_count, 8) * 0.015)
        rejected_reason = None
        if not clipped:
            rejected_reason = "invalid_or_empty_bbox"
            score = 0.0
        elif score < 0.45:
            rejected_reason = "low_confidence_evidence"
        return {
            "candidate_id": candidate_id,
            "strategy": strategy,
            "bbox": clipped,
            "page_number": 1,
            "score": round(score, 4),
            "signals": {
                **signals,
                "anchor_text_count": len(anchors),
                "target_code_count": class_code_count,
                "detected_target_codes": sorted(str(code) for code in target_codes if code),
            },
            "selected": False,
            "rejected_reason": rejected_reason,
        }

    if page_width <= 0 or page_height <= 0:
        return {
            "bbox": None,
            "confidence": 0.0,
            "strategy": "unavailable_no_page_dimensions",
            "anchor_text_count": 0,
            "target_code_count_estimate": 0,
            "legend_candidates": [],
        }

    target_codes = set(TARGET_CODE_CLASSES)
    keyword_texts = [
        row
        for row in text_specs
        if (bbox := row.get("bbox_page_pt"))
        and page_height * 0.18 <= bbox[1] <= page_height * 0.94
        and any(keyword in str(row.get("raw_text") or "").lower() for keyword in ["legenda", "ploch", "stav", "návrh", "navrh", "stabil"])
    ]
    target_left_codes = [
        row
        for row in text_specs
        if row.get("matched_code_candidate") in target_codes
        and (bbox := row.get("bbox_page_pt"))
        and bbox[0] <= page_width * 0.16
        and page_height * 0.34 <= bbox[1] <= page_height * 0.84
    ]
    detected_left_codes = {row.get("matched_code_candidate") for row in target_left_codes}
    candidates: list[dict[str, Any]] = []
    if len(target_left_codes) >= 8 and len(detected_left_codes) >= 5:
        min_x = min(float(row["bbox_page_pt"][0]) for row in target_left_codes)
        min_y = min(float(row["bbox_page_pt"][1]) for row in target_left_codes)
        max_x = max(float(row["bbox_page_pt"][2]) for row in target_left_codes)
        max_y = max(float(row["bbox_page_pt"][3]) for row in target_left_codes)
        label_right = [
            float(row["bbox_page_pt"][2])
            for row in text_specs
            if (bbox := row.get("bbox_page_pt"))
            and bbox[0] <= page_width * 0.16
            and min_y - 80 <= bbox[1] <= max_y + 80
        ]
        header_y = min(
            [
                float(row["bbox_page_pt"][1])
                for row in text_specs
                if (bbox := row.get("bbox_page_pt"))
                and bbox[0] <= page_width * 0.16
                and max(0, min_y - 180) <= bbox[1] <= min_y
                and (row.get("raw_text") or "").strip()
            ]
            or [min_y]
        )
        bbox = [
            max(0.0, min_x - 85.0),
            max(0.0, header_y - 55.0),
            min(page_width, max(max(label_right or [max_x]), max_x) + 90.0),
            min(page_height, max_y + 75.0),
        ]
        candidates.append(
            candidate_record(
                candidate_id="legend-candidate-left-code-cluster-0001",
                strategy="target_left_legend_code_cluster_v1",
                bbox=bbox,
                anchors=target_left_codes,
                base_score=0.68,
                signals={
                    "class_code_cluster": True,
                    "left_margin_cluster": True,
                    "keyword_text_count": sum(1 for row in keyword_texts if row.get("bbox_page_pt") and bbox_contains_point(bbox, bbox_center(row.get("bbox_page_pt")))),
                    "symbol_grid_hint": True,
                    "text_density_hint": len(target_left_codes),
                },
            )
        )

    all_target_texts = [
        row
        for row in text_specs
        if row.get("matched_code_candidate") in target_codes and row.get("bbox_page_pt")
    ]
    if len(all_target_texts) >= 6:
        min_x = min(float(row["bbox_page_pt"][0]) for row in all_target_texts)
        min_y = min(float(row["bbox_page_pt"][1]) for row in all_target_texts)
        max_x = max(float(row["bbox_page_pt"][2]) for row in all_target_texts)
        max_y = max(float(row["bbox_page_pt"][3]) for row in all_target_texts)
        bbox = [
            max(0.0, min_x - 110.0),
            max(0.0, min_y - 90.0),
            min(page_width, max_x + 160.0),
            min(page_height, max_y + 95.0),
        ]
        candidates.append(
            candidate_record(
                candidate_id="legend-candidate-global-code-cluster-0001",
                strategy="target_code_global_cluster_v1",
                bbox=bbox,
                anchors=all_target_texts,
                base_score=0.46,
                signals={
                    "class_code_cluster": True,
                    "keyword_text_count": sum(1 for row in keyword_texts if row.get("bbox_page_pt") and bbox_contains_point(bbox, bbox_center(row.get("bbox_page_pt")))),
                    "text_density_hint": len(all_target_texts),
                    "symbol_grid_hint": len(all_target_texts) >= 10,
                },
            )
        )

    right_panel = [
        row
        for row in text_specs
        if (bbox := row.get("bbox_page_pt"))
        and bbox[0] >= page_width * 0.84
        and page_height * 0.48 <= bbox[1] <= page_height * 0.9
    ]
    target_texts = [
        row
        for row in text_specs
        if row.get("matched_code_candidate") and (bbox := row.get("bbox_page_pt")) and bbox[0] >= page_width * 0.70
    ]
    anchors = right_panel if len(right_panel) >= 6 else target_texts
    strategy = "right_panel_text_density_v1" if len(right_panel) >= 6 else "target_code_right_cluster_v1"
    if anchors:
        min_x = min(float(row["bbox_page_pt"][0]) for row in anchors)
        min_y = min(float(row["bbox_page_pt"][1]) for row in anchors)
        max_x = max(float(row["bbox_page_pt"][2]) for row in anchors)
        max_y = max(float(row["bbox_page_pt"][3]) for row in anchors)
        bbox = [
            max(0.0, min_x - 160.0),
            max(0.0, min_y - 120.0),
            min(page_width, max_x + 80.0),
            min(page_height, max_y + 90.0),
        ]
        candidates.append(
            candidate_record(
                candidate_id="legend-candidate-right-density-0001",
                strategy=strategy,
                bbox=bbox,
                anchors=anchors,
                base_score=0.58 if len(right_panel) >= 6 else 0.40,
                signals={
                    "right_panel_density": len(right_panel),
                    "class_code_cluster": bool(target_texts),
                    "keyword_text_count": sum(1 for row in keyword_texts if row.get("bbox_page_pt") and bbox_contains_point(bbox, bbox_center(row.get("bbox_page_pt")))),
                    "text_density_hint": len(anchors),
                },
            )
        )

    if len(keyword_texts) >= 4:
        min_x = min(float(row["bbox_page_pt"][0]) for row in keyword_texts)
        min_y = min(float(row["bbox_page_pt"][1]) for row in keyword_texts)
        max_x = max(float(row["bbox_page_pt"][2]) for row in keyword_texts)
        max_y = max(float(row["bbox_page_pt"][3]) for row in keyword_texts)
        bbox = [
            max(0.0, min_x - 120.0),
            max(0.0, min_y - 80.0),
            min(page_width, max_x + 160.0),
            min(page_height, max_y + 90.0),
        ]
        candidates.append(
            candidate_record(
                candidate_id="legend-candidate-keyword-density-0001",
                strategy="legend_keyword_density_v1",
                bbox=bbox,
                anchors=keyword_texts,
                base_score=0.38,
                signals={
                    "text_keywords": ["legenda", "plochy", "stav", "navrh"],
                    "keyword_text_count": len(keyword_texts),
                    "text_density_hint": len(keyword_texts),
                    "class_code_cluster": False,
                },
            )
        )

    candidates.sort(key=lambda row: float(row.get("score") or 0.0), reverse=True)
    selected = next((row for row in candidates if not row.get("rejected_reason")), None)
    if selected:
        selected["selected"] = True
    selected_bbox = selected.get("bbox") if selected else None
    selected_signals = selected.get("signals") if selected else {}
    return {
        "bbox": selected_bbox,
        "confidence": float(selected.get("score") if selected else 0.0),
        "strategy": selected.get("strategy") if selected else "legend_candidate_unavailable_low_confidence_v8_1",
        "anchor_text_count": int(selected_signals.get("anchor_text_count") or 0),
        "target_code_count_estimate": int(selected_signals.get("target_code_count") or 0),
        "column_count_estimate": 1 if selected_bbox else 0,
        "legend_column_bboxes_page_pt": [selected_bbox] if selected_bbox else [],
        "detected_target_codes": selected_signals.get("detected_target_codes", []),
        "legend_candidates": candidates,
        "selection_threshold": 0.45,
        "algorithm": "legend_candidate_evidence_ranker_v8_1",
    }


def classify_feature_region(
    bbox: list[float] | None,
    *,
    page_width: float,
    page_height: float,
    legend_bbox: list[float] | None,
) -> str:
    center = bbox_center(bbox)
    if bbox and legend_bbox:
        overlap = bbox_intersection_area(bbox, legend_bbox)
        if bbox_contains_point(legend_bbox, center) or overlap >= max(4.0, bbox_area(bbox) * 0.2):
            return "legend_candidate_region"
    if center and page_height > 0 and center[1] <= page_height * 0.075:
        return "title_block_region"
    if center and page_height > 0 and center[1] >= page_height * 0.92:
        return "title_block_region"
    if center and page_width > 0 and page_height > 0 and center[0] >= page_width * 0.9 and center[1] <= page_height * 0.48:
        return "title_block_region"
    if center and page_width > 0 and page_height > 0 and center[0] >= page_width * 0.88 and center[1] >= page_height * 0.65:
        return "legend_or_title_margin_region"
    return "map_body_region"


def classify_source_regions(
    features: list[dict[str, Any]],
    *,
    page_width: float,
    page_height: float,
    legend_bbox: list[float] | None,
) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for feature in features:
        props = feature.setdefault("properties", {})
        region = classify_feature_region(feature_bbox(feature), page_width=page_width, page_height=page_height, legend_bbox=legend_bbox)
        props["source_region_class"] = region
        counts[region] += 1
    return {
        "region_counts": dict(counts),
        "legend_bbox_page_pt": legend_bbox,
        "map_body_feature_count": counts.get("map_body_region", 0),
        "legend_candidate_feature_count": counts.get("legend_candidate_region", 0),
    }


def analyze_tessellation_fragments(
    features: list[dict[str, Any]],
    *,
    page_width: float,
    page_height: float,
) -> dict[str, Any]:
    areas = [geometry_area(feature.get("geometry") or {}) for feature in features]
    bboxes = [feature_bbox(feature) for feature in features]
    heights = [max(0.0, bbox[3] - bbox[1]) for bbox in bboxes if bbox]
    widths = [max(0.0, bbox[2] - bbox[0]) for bbox in bboxes if bbox]
    raw_count = len(features)
    median_area = median_float(areas)
    median_height = median_float(heights)
    style_counts: Counter[str] = Counter(
        str((feature.get("properties") or {}).get("source_style_hex") or "none")
        for feature in features
    )
    triangle_count = sum(1 for feature in features if feature_exterior_point_count(feature) <= 4)
    tiny_height_count = sum(1 for height in heights if height <= max(3.0, median_height * 1.6 if median_height else 3.0))
    tiny_area_count = sum(1 for area in areas if area <= max(20.0, median_area * 2.0 if median_area else 20.0))
    y_bands: Counter[int] = Counter()
    for bbox in bboxes:
        center = bbox_center(bbox)
        if center:
            y_bands[int(round(center[1] * 2))] += 1
    dense_band_hits = sum(count for _band, count in y_bands.most_common(50))
    page_area = max(page_width * page_height, 1.0)
    tiny_height_ratio = tiny_height_count / raw_count if raw_count else 0.0
    tiny_area_ratio = tiny_area_count / raw_count if raw_count else 0.0
    triangular_ratio = triangle_count / raw_count if raw_count else 0.0
    horizontal_band_alignment_score = dense_band_hits / raw_count if raw_count else 0.0
    same_style_fragment_density = max(style_counts.values(), default=0) / raw_count if raw_count else 0.0
    visual_fragmentation_score = min(
        1.0,
        (0.30 * tiny_height_ratio)
        + (0.25 * tiny_area_ratio)
        + (0.25 * triangular_ratio)
        + (0.10 * same_style_fragment_density)
        + (0.10 * min(1.0, raw_count / 30000)),
    )
    stripe_artifact_score = min(
        1.0,
        (0.45 * tiny_height_ratio)
        + (0.35 * triangular_ratio)
        + (0.10 * horizontal_band_alignment_score)
        + (0.10 * min(1.0, raw_count / max(page_area / 500, 1.0))),
    )
    tessellated_fill_score = max(visual_fragmentation_score, stripe_artifact_score)
    detected = raw_count >= 10000 and median_area <= 30.0 and tiny_height_ratio >= 0.55 and triangular_ratio >= 0.65
    reason = (
        f"raw_count={raw_count}, median_area={median_area:.3f}, median_height={median_height:.3f}, "
        f"tiny_height_ratio={tiny_height_ratio:.3f}, triangular_ratio={triangular_ratio:.3f}"
    )
    return {
        "raw_fragment_count": raw_count,
        "raw_fragment_count_by_style": dict(style_counts.most_common(30)),
        "median_fragment_area": median_area,
        "median_fragment_bbox_height": median_height,
        "median_fragment_bbox_width": median_float(widths),
        "tiny_fragment_ratio": max(tiny_height_ratio, tiny_area_ratio),
        "tiny_height_ratio": tiny_height_ratio,
        "tiny_area_ratio": tiny_area_ratio,
        "same_style_fragment_density": same_style_fragment_density,
        "horizontal_band_alignment_score": horizontal_band_alignment_score,
        "triangular_fragment_ratio": triangular_ratio,
        "stripe_artifact_score": stripe_artifact_score,
        "visual_fragmentation_score": visual_fragmentation_score,
        "tessellated_fill_detected": detected,
        "tessellated_fill_score": tessellated_fill_score,
        "tessellated_fill_reason": reason,
        "candidate_merge_required": detected,
        "primary_extraction_mode": "merged_polygons" if detected else "raw_polygons",
    }


def _polygon_geometries_from_shape(shape: Any) -> list[Any]:
    if shape is None or getattr(shape, "is_empty", True):
        return []
    geom_type = getattr(shape, "geom_type", "")
    if geom_type == "Polygon":
        return [shape]
    if geom_type == "MultiPolygon":
        return [geom for geom in shape.geoms if not geom.is_empty]
    if geom_type == "GeometryCollection":
        polygons: list[Any] = []
        for geom in shape.geoms:
            polygons.extend(_polygon_geometries_from_shape(geom))
        return polygons
    return []


def _feature_to_shapely_polygon(feature: dict[str, Any]) -> Any | None:
    if Polygon is None:
        return None
    geom = feature.get("geometry") or {}
    if geom.get("type") != "Polygon":
        return None
    coordinates = geom.get("coordinates") or []
    if not coordinates:
        return None
    try:
        polygon = Polygon(coordinates[0], coordinates[1:])
        if polygon.is_empty or polygon.area <= 0:
            return None
        if not polygon.is_valid and make_valid is not None:
            polygon = make_valid(polygon)
        return polygon
    except Exception:
        return None


def _hex_rgb(value: str | None) -> tuple[int, int, int] | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip().lstrip("#")
    if len(text) != 6:
        return None
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return None


def is_near_white(value: str | None) -> bool:
    rgb = _hex_rgb(value)
    if not rgb:
        return False
    return min(rgb) >= 242 and max(rgb) - min(rgb) <= 10


def is_near_black(value: str | None) -> bool:
    rgb = _hex_rgb(value)
    if not rgb:
        return False
    return max(rgb) <= 35 and max(rgb) - min(rgb) <= 20


def ring_area(points: list[Any]) -> float:
    if len(points) < 4:
        return 0.0
    area = 0.0
    for index in range(len(points) - 1):
        x1, y1 = points[index][:2]
        x2, y2 = points[index + 1][:2]
        area += (float(x1) * float(y2)) - (float(x2) * float(y1))
    return abs(area) / 2.0


def ring_perimeter(points: list[Any]) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for index in range(len(points) - 1):
        x1, y1 = points[index][:2]
        x2, y2 = points[index + 1][:2]
        total += math.hypot(float(x2) - float(x1), float(y2) - float(y1))
    return total


def small_angle_count(points: list[Any], *, threshold_degrees: float = 18.0) -> int:
    if len(points) < 5:
        return 0
    count = 0
    ring = points[:-1] if points[0] == points[-1] else points
    for index, point in enumerate(ring):
        prev = ring[index - 1]
        nxt = ring[(index + 1) % len(ring)]
        ax = float(prev[0]) - float(point[0])
        ay = float(prev[1]) - float(point[1])
        bx = float(nxt[0]) - float(point[0])
        by = float(nxt[1]) - float(point[1])
        denom = max(math.hypot(ax, ay) * math.hypot(bx, by), 1e-9)
        cos_value = max(-1.0, min(1.0, (ax * bx + ay * by) / denom))
        angle = math.degrees(math.acos(cos_value))
        if angle <= threshold_degrees:
            count += 1
    return count


def polygon_outer_ring(feature: dict[str, Any]) -> list[Any]:
    geom = feature.get("geometry") or {}
    coordinates = geom.get("coordinates") or []
    if geom.get("type") == "Polygon" and coordinates:
        return list(coordinates[0] or [])
    if geom.get("type") == "MultiPolygon" and coordinates and coordinates[0]:
        return list(coordinates[0][0] or [])
    return []


def feature_shape_metrics(feature: dict[str, Any]) -> dict[str, Any]:
    bbox = feature_bbox(feature)
    width = max(0.0, (bbox[2] - bbox[0]) if bbox else 0.0)
    height = max(0.0, (bbox[3] - bbox[1]) if bbox else 0.0)
    min_width = min(width, height) if width and height else 0.0
    aspect = max(width, height) / max(min_width, 1e-9) if width and height else 0.0
    area = geometry_area(feature.get("geometry") or {})
    ring = polygon_outer_ring(feature)
    perimeter = ring_perimeter(ring)
    compactness = (4.0 * math.pi * area / (perimeter * perimeter)) if perimeter > 0 and area > 0 else 0.0
    angle_count = small_angle_count(ring)
    vertex_count = max(0, len(ring) - 1)
    boundary_complexity = vertex_count / max(math.sqrt(max(area, 1.0)), 1.0)
    spike_score = min(
        1.0,
        (0.35 * min(aspect / 30.0, 1.0))
        + (0.30 * min(angle_count / 6.0, 1.0))
        + (0.20 * (1.0 - min(compactness / 0.18, 1.0)))
        + (0.15 * min(boundary_complexity / 18.0, 1.0)),
    )
    return {
        "spike_score": round(spike_score, 4),
        "needle_count": 1 if spike_score >= 0.74 and aspect >= 20 else 0,
        "sliver_component_count": 1 if compactness <= 0.035 and aspect >= 12 else 0,
        "thin_corridor_count": 1 if min_width > 0 and min_width <= 2.5 and area >= 20 else 0,
        "min_width_estimate": round(min_width, 3),
        "compactness_score": round(compactness, 4),
        "oriented_bbox_aspect_ratio": round(aspect, 3),
        "boundary_complexity_score": round(boundary_complexity, 4),
        "small_angle_vertex_count": angle_count,
    }


def feature_void_metrics(feature: dict[str, Any]) -> dict[str, Any]:
    geom = feature.get("geometry") or {}
    coordinates = geom.get("coordinates") or []
    if geom.get("type") != "Polygon" or not coordinates:
        return {
            "triangular_void_count": 0,
            "small_void_count": 0,
            "void_area_ratio": 0.0,
            "void_source_fragment_role": None,
            "void_matches_original_plan": "not_applicable",
            "void_removed_as_artifact_count": 0,
            "void_kept_count": 0,
            "void_requires_review_count": 0,
        }
    outer_area = ring_area(list(coordinates[0] or []))
    hole_areas: list[float] = []
    triangular = 0
    small = 0
    for hole in coordinates[1:]:
        ring = list(hole or [])
        hole_area = ring_area(ring)
        if hole_area <= 0:
            continue
        hole_areas.append(hole_area)
        vertices = max(0, len(ring) - 1)
        hole_bbox = geometry_bbox({"type": "Polygon", "coordinates": [hole]})
        width = max(0.0, hole_bbox[2] - hole_bbox[0]) if hole_bbox else 0.0
        height = max(0.0, hole_bbox[3] - hole_bbox[1]) if hole_bbox else 0.0
        if vertices <= 3:
            triangular += 1
        if hole_area <= 35.0 or min(width, height) <= 2.5:
            small += 1
    total_hole_area = sum(hole_areas)
    ratio = total_hole_area / max(outer_area, 1.0)
    review_count = triangular + small
    return {
        "triangular_void_count": triangular,
        "small_void_count": small,
        "void_area_ratio": round(ratio, 6),
        "void_source_fragment_role": "interior_ring_from_merged_fill" if hole_areas else None,
        "void_matches_original_plan": "requires_plan_visual_review" if review_count else "not_applicable",
        "void_removed_as_artifact_count": 0,
        "void_kept_count": len(hole_areas),
        "void_requires_review_count": review_count,
    }


HOLE_CLEANUP_THRESHOLDS = {
    "rectangularity_min": 0.82,
    "area_ratio_max": 0.018,
    "small_area_max": 35.0,
    "thin_width_max": 2.5,
    "text_overlap_required": False,
    "white_fill_evidence_required": False,
}


def classify_feature_holes(feature: dict[str, Any]) -> dict[str, Any]:
    geom = feature.get("geometry") or {}
    coordinates = geom.get("coordinates") or []
    if geom.get("type") != "Polygon" or not coordinates:
        return {
            "holes": [],
            "hole_cleanup": {
                "applied_to_candidate": False,
                "raw_preserved": True,
                "removed_hole_count": 0,
                "kept_hole_count": 0,
                "review_required_hole_count": 0,
                "reason": "geometry has no polygon holes",
                "thresholds": HOLE_CLEANUP_THRESHOLDS,
            },
            "hole_type_counts": {},
        }
    outer_area = max(ring_area(list(coordinates[0] or [])), 1.0)
    holes: list[dict[str, Any]] = []
    type_counts: Counter[str] = Counter()
    removable_types = {"label_mask_rectangle", "hatch_grid_artifact", "white_background_artifact"}
    for index, hole in enumerate(coordinates[1:], 1):
        ring = list(hole or [])
        area = ring_area(ring)
        bbox = geometry_bbox({"type": "Polygon", "coordinates": [ring]})
        width = max(0.0, bbox[2] - bbox[0]) if bbox else 0.0
        height = max(0.0, bbox[3] - bbox[1]) if bbox else 0.0
        bbox_area_value = max(width * height, 1e-9)
        rectangularity = area / bbox_area_value
        area_ratio = area / outer_area
        vertices = max(0, len(ring) - 1)
        if rectangularity >= HOLE_CLEANUP_THRESHOLDS["rectangularity_min"] and area_ratio <= HOLE_CLEANUP_THRESHOLDS["area_ratio_max"]:
            hole_type = "label_mask_rectangle"
            confidence = "high" if area_ratio <= 0.006 else "medium"
            reason = "rectangular interior ring with small parent-area ratio"
        elif vertices <= 3 or area <= HOLE_CLEANUP_THRESHOLDS["small_area_max"] or min(width, height) <= HOLE_CLEANUP_THRESHOLDS["thin_width_max"]:
            hole_type = "hatch_grid_artifact"
            confidence = "medium"
            reason = "tiny, triangular, or very thin interior ring consistent with hatch/grid artifact"
        elif rectangularity >= 0.72 and area_ratio <= 0.03:
            hole_type = "white_background_artifact"
            confidence = "medium"
            reason = "near-rectangular void likely caused by white background/mask drawing"
        elif area_ratio >= 0.025 and rectangularity < 0.55:
            hole_type = "real_planning_void"
            confidence = "low"
            reason = "large non-rectangular void may be a legitimate planning exclusion"
        else:
            hole_type = "unknown_review_required"
            confidence = "low"
            reason = "hole evidence is ambiguous and must be reviewed"
        type_counts[hole_type] += 1
        holes.append(
            {
                "hole_index": index,
                "hole_type": hole_type,
                "confidence": confidence,
                "area": round(area, 3),
                "area_ratio": round(area_ratio, 6),
                "bbox": [round(value, 3) for value in bbox] if bbox else None,
                "width": round(width, 3),
                "height": round(height, 3),
                "rectangularity": round(rectangularity, 4),
                "vertices": vertices,
                "reason": reason,
                "candidate_removable": hole_type in removable_types,
            }
        )
    removed_count = sum(1 for hole in holes if hole["candidate_removable"])
    review_count = sum(1 for hole in holes if hole["hole_type"] == "unknown_review_required")
    return {
        "holes": holes,
        "hole_cleanup": {
            "applied_to_candidate": removed_count > 0,
            "raw_preserved": True,
            "removed_hole_count": removed_count,
            "kept_hole_count": len(holes) - removed_count,
            "review_required_hole_count": review_count,
            "reason": "only label-mask, white-background, and hatch-grid hole candidates are removed from review candidate geometry",
            "thresholds": HOLE_CLEANUP_THRESHOLDS,
        },
        "hole_type_counts": dict(type_counts),
    }


def geometry_component_metrics(feature: dict[str, Any]) -> dict[str, Any]:
    geom = feature.get("geometry") or {}
    coordinates = geom.get("coordinates") or []
    component_areas: list[float] = []
    ring_count = 0
    if geom.get("type") == "Polygon":
        ring_count = len(coordinates)
        if coordinates:
            component_areas.append(ring_area(list(coordinates[0] or [])))
    elif geom.get("type") == "MultiPolygon":
        for polygon in coordinates:
            if not polygon:
                continue
            ring_count += len(polygon)
            component_areas.append(ring_area(list(polygon[0] or [])))
    total_area = sum(component_areas)
    tiny_islands = sum(1 for area in component_areas[1:] if total_area and area / max(total_area, 1.0) <= 0.01)
    return {
        "component_count_before": len(component_areas),
        "component_count_after": len(component_areas),
        "island_count": tiny_islands,
        "disconnected_selected_border_component_count": max(0, ring_count - 1),
    }


def cleaned_candidate_geometry_for_review(feature: dict[str, Any]) -> dict[str, Any] | None:
    geom = feature.get("geometry") or {}
    coordinates = geom.get("coordinates") or []
    if geom.get("type") != "Polygon" or not coordinates:
        return None
    hole_classification = classify_feature_holes(feature)
    by_index = {row["hole_index"]: row for row in hole_classification["holes"]}
    outer = list(coordinates[0] or [])
    kept_holes = []
    removed: list[dict[str, Any]] = []
    for index, hole in enumerate(coordinates[1:], 1):
        ring = list(hole or [])
        classification = by_index.get(index, {})
        if classification.get("candidate_removable"):
            removed.append(
                {
                    "hole_index": index,
                    "hole_type": classification.get("hole_type"),
                    "area": classification.get("area"),
                    "area_ratio": classification.get("area_ratio"),
                    "vertices": classification.get("vertices"),
                    "bbox": classification.get("bbox"),
                    "reason": classification.get("reason"),
                }
            )
        else:
            kept_holes.append(ring)
    if not removed:
        return None
    return {
        "type": "Polygon",
        "coordinates": [outer, *kept_holes],
        "review_candidate_metadata": {
            "algorithm": "review_candidate_remove_label_mask_white_background_hatch_grid_holes_v8_2",
            "removed_void_count": len(removed),
            "removed_voids": removed,
            "hole_type_counts": hole_classification["hole_type_counts"],
            "hole_cleanup": hole_classification["hole_cleanup"],
            "raw_geometry_unchanged": True,
            "export_requires_human_approval": True,
        },
    }


def geometry_hole_metrics(features: list[dict[str, Any]]) -> dict[str, Any]:
    rectangular_hole_count = 0
    rectangular_hole_area = 0.0
    total_area = sum(geometry_area(feature.get("geometry") or {}) for feature in features)
    holes_kept = 0
    triangular_void_count = 0
    small_void_count = 0
    void_area = 0.0
    void_review_required = 0
    for feature in features:
        void_metrics = feature_void_metrics(feature)
        triangular_void_count += int(void_metrics["triangular_void_count"])
        small_void_count += int(void_metrics["small_void_count"])
        void_review_required += int(void_metrics["void_requires_review_count"])
        geom = feature.get("geometry") or {}
        polygons = geom.get("coordinates") or []
        if geom.get("type") != "Polygon":
            continue
        for hole in polygons[1:]:
            holes_kept += 1
            hole_area = ring_area(list(hole or []))
            void_area += hole_area
            hole_bbox = geometry_bbox({"type": "Polygon", "coordinates": [hole]})
            width = max(0.0, hole_bbox[2] - hole_bbox[0]) if hole_bbox else 0.0
            height = max(0.0, hole_bbox[3] - hole_bbox[1]) if hole_bbox else 0.0
            bbox_area_value = width * height
            is_rectangular = bool(hole_area and bbox_area_value and abs(hole_area - bbox_area_value) / max(bbox_area_value, 1.0) <= 0.08)
            if is_rectangular:
                rectangular_hole_count += 1
                rectangular_hole_area += hole_area
    ratio = rectangular_hole_area / max(total_area + rectangular_hole_area, 1.0)
    void_ratio = void_area / max(total_area + void_area, 1.0)
    return {
        "rectangular_hole_count": rectangular_hole_count,
        "rectangular_hole_area": round(rectangular_hole_area, 3),
        "rectangular_hole_area_ratio": round(ratio, 6),
        "holes_removed_as_artifacts_count": 0,
        "holes_kept_count": holes_kept,
        "hole_review_required_count": rectangular_hole_count if ratio >= 0.025 else 0,
        "triangular_void_count": triangular_void_count,
        "small_void_count": small_void_count,
        "void_area_ratio": round(void_ratio, 6),
        "void_source_fragment_role": "interior_ring_from_merged_fill" if holes_kept else None,
        "void_matches_original_plan": "requires_plan_visual_review" if void_review_required else "not_applicable",
        "void_removed_as_artifact_count": 0,
        "void_kept_count": holes_kept,
        "void_requires_review_count": void_review_required,
    }


def classify_fragment_roles(
    features: list[dict[str, Any]],
    *,
    page_width: float,
    page_height: float,
    tessellation: dict[str, Any],
) -> dict[str, Any]:
    role_counts: Counter[str] = Counter()
    role_area: Counter[str] = Counter()
    page_area = max(page_width * page_height, 1.0)
    median_height = float(tessellation.get("median_fragment_bbox_height") or 0.0)
    median_area = float(tessellation.get("median_fragment_area") or 0.0)
    for feature in features:
        props = feature.setdefault("properties", {})
        bbox = feature_bbox(feature)
        area = geometry_area(feature.get("geometry") or {})
        bbox_h = max(0.0, bbox[3] - bbox[1]) if bbox else 0.0
        bbox_w = max(0.0, bbox[2] - bbox[0]) if bbox else 0.0
        style = props.get("source_style_hex")
        region = props.get("source_region_class")
        counts = props.get("source_path_item_type_counts") or {}
        if region == "legend_candidate_region":
            role = "legend_symbol_fragment"
        elif is_near_white(str(style) if style else None) and bbox_area(bbox) >= page_area * 0.5:
            role = "background_mask_fragment"
        elif is_near_white(str(style) if style else None):
            role = "text_mask_fragment"
        elif not style and props.get("source_stroke_hex"):
            role = "linework_fragment"
        elif counts.get("re") and area <= max(30.0, median_area * 4.0 if median_area else 30.0):
            role = "hatch_fragment"
        elif tessellation.get("tessellated_fill_detected") and (
            feature_exterior_point_count(feature) <= 4
            or bbox_h <= max(3.0, median_height * 1.8 if median_height else 3.0)
            or min(bbox_w, bbox_h) <= 1.5
        ):
            role = "tessellated_area_fragment"
        elif region == "map_body_region":
            role = "area_fill_candidate"
        else:
            role = "unknown_fragment"
        props["fragment_role"] = role
        props["trusted_merge_input"] = role in {"area_fill_candidate", "tessellated_area_fragment"}
        role_counts[role] += 1
        role_area[role] += area
    return {
        "algorithm": "fragment_role_classification_v1",
        "fragment_role_counts": dict(role_counts),
        "fragment_role_area": {key: round(value, 3) for key, value in role_area.items()},
        "trusted_merge_input_count": sum(1 for feature in features if (feature.get("properties") or {}).get("trusted_merge_input")),
        "trusted_merge_roles": ["area_fill_candidate", "tessellated_area_fragment"],
    }


def annotate_primary_features(
    features: list[dict[str, Any]],
    *,
    legend_items: list[dict[str, Any]],
    legend_vector_definitions: list[dict[str, Any]],
) -> dict[str, Any]:
    items_by_code = {str(item.get("code_text")): item for item in legend_items if item.get("code_text")}
    vector_defs_by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in legend_vector_definitions:
        if row.get("legend_item_id"):
            vector_defs_by_item[str(row["legend_item_id"])].append(row)
    proposal_count = 0
    artifact_review_count = 0
    unmapped_count = 0
    for feature in features:
        props = feature.setdefault("properties", {})
        metrics = feature_shape_metrics(feature)
        void_metrics = feature_void_metrics(feature)
        component_metrics = geometry_component_metrics(feature)
        hole_classification = classify_feature_holes(feature)
        cleaned_candidate = cleaned_candidate_geometry_for_review(feature)
        props.update(metrics)
        props.update(void_metrics)
        props.update(component_metrics)
        props["hole_types"] = hole_classification["holes"][:80]
        props["hole_type_counts"] = hole_classification["hole_type_counts"]
        props["hole_cleanup"] = hole_classification["hole_cleanup"]
        props.setdefault("source_fill_hex", props.get("source_style_hex"))
        props.setdefault("source_stroke_hex", props.get("source_stroke_hex"))
        props.setdefault("source_fill_opacity", props.get("source_fill_opacity"))
        props.setdefault("source_stroke_opacity", props.get("source_stroke_opacity"))
        props.setdefault("source_style_group_id", props.get("merged_group_id"))
        flags: list[str] = []
        if is_near_white(str(props.get("source_style_hex")) if props.get("source_style_hex") else None):
            flags.append("white_fill_candidate")
        if metrics["spike_score"] >= 0.74 or metrics["needle_count"] or metrics["sliver_component_count"]:
            flags.append("artifact_requires_review")
            if metrics["needle_count"]:
                flags.append("needle_spike_candidate")
            if metrics["sliver_component_count"]:
                flags.append("sliver_component_candidate")
        if void_metrics["void_requires_review_count"]:
            flags.append("artifact_requires_review")
            flags.append("void_artifact_candidate")
        if hole_classification["hole_cleanup"]["review_required_hole_count"]:
            flags.append("artifact_requires_review")
            flags.append("unknown_hole_review_required")
        if metrics["thin_corridor_count"]:
            flags.append("artifact_requires_review")
            flags.append("thin_corridor_candidate")
        if component_metrics["island_count"]:
            flags.append("artifact_requires_review")
            flags.append("tiny_island_candidate")
        target_code = props.get("target_code_candidate")
        legend_item = items_by_code.get(str(target_code)) if target_code else None
        item_vector_defs = vector_defs_by_item.get(str(legend_item.get("legend_item_id"))) if legend_item else []
        matched_vector_def = item_vector_defs[0] if item_vector_defs else None
        props["raw_LAYER"] = props.get("LAYER")
        props["raw_CLASS"] = props.get("CLASS")
        props["raw_TYPE"] = props.get("TYPE")
        props["raw_LAYER_CLASS"] = props.get("LAYER_CLASS")
        if target_code:
            props["proposed_LAYER"] = "RZVP"
            props["proposed_CLASS"] = target_code
            props["proposed_TYPE"] = props.get("TYPE") if props.get("TYPE") != "UNMAPPED" else "UNMAPPED"
            props["proposed_LAYER_CLASS"] = f"RZVP.{target_code}"
            props["classification_reason"] = f"matched nearby target text {props.get('source_text_nearby') or target_code}"
            props["matched_legend_item_id"] = legend_item.get("legend_item_id") if legend_item else None
            props["matched_vector_def_id"] = matched_vector_def.get("vector_def_id") if matched_vector_def else None
            proposal_count += 1
        else:
            props["proposed_LAYER"] = "UNMAPPED"
            props["proposed_CLASS"] = "UNMAPPED"
            props["proposed_TYPE"] = "UNMAPPED"
            props["proposed_LAYER_CLASS"] = "UNMAPPED.UNMAPPED"
            props["classification_reason"] = "no legend/text/style evidence matched target scope"
            props["matched_legend_item_id"] = None
            props["matched_vector_def_id"] = None
            unmapped_count += 1
        props["source_vector_def_id"] = props.get("matched_vector_def_id")
        props["legend_symbol_fill_hex"] = matched_vector_def.get("fill_color_hex") if matched_vector_def else None
        props["legend_symbol_stroke_hex"] = matched_vector_def.get("stroke_color_hex") if matched_vector_def else None
        source_fill = props.get("source_fill_hex") or props.get("source_style_hex")
        legend_fill = props.get("legend_symbol_fill_hex")
        proposed_fill = CLASS_DISPLAY_COLORS.get(str(props.get("proposed_CLASS")), CLASS_DISPLAY_COLORS["UNMAPPED"])
        if source_fill and not is_near_white(str(source_fill)):
            props["display_fill_hex"] = source_fill
            props["display_color_source"] = "source_style"
        elif legend_fill:
            props["display_fill_hex"] = legend_fill
            props["display_color_source"] = "legend_symbol"
        elif props.get("proposed_CLASS") != "UNMAPPED":
            props["display_fill_hex"] = proposed_fill
            props["display_color_source"] = "proposed_class"
        else:
            props["display_fill_hex"] = CLASS_DISPLAY_COLORS["UNMAPPED"]
            props["display_color_source"] = "fallback_unmapped"
        props["display_stroke_hex"] = props.get("legend_symbol_stroke_hex") or props.get("source_stroke_hex") or "#222222"
        props["artifact_trust_state"] = "review_only" if flags else "mapping_review_required"
        artifact_component_count = (
            int(metrics["needle_count"])
            + int(metrics["sliver_component_count"])
            + int(metrics["thin_corridor_count"])
            + int(void_metrics["void_requires_review_count"])
            + int(component_metrics["island_count"])
            + int(hole_classification["hole_cleanup"]["review_required_hole_count"])
        )
        props["artifact_component_count"] = artifact_component_count
        props["geometry_decision"] = "artifact blocked" if flags else "needs review"
        props["geometry_decision_reason"] = (
            "artifact evidence detected: " + ", ".join(sorted(set(flags)))
            if flags
            else "no spike, sliver, void, island, or thin-corridor threshold exceeded; mapping still requires review"
        )
        props["review_required"] = True
        props["cleanup_applied"] = False
        props["geometry_cleanup_algorithm"] = "geometry_artifact_review_flagging_v1+review_candidate_remove_label_mask_white_background_hatch_grid_holes_v8_2"
        props["geometry_cleanup_tolerance"] = 0.0
        props["geometry_cleanup_reason"] = (
            "no automatic geometry mutation; void/spike/thin-corridor evidence requires human review"
            if flags
            else "no artifact cleanup evidence exceeded the review threshold"
        )
        props["cleanup_before_summary"] = (
            f"area={round(geometry_area(feature.get('geometry') or {}), 3)} holes={void_metrics['void_kept_count']} "
            f"spike={metrics['spike_score']} thin_corridors={metrics['thin_corridor_count']}"
        )
        props["cleanup_after_summary"] = props["cleanup_before_summary"]
        props["cleaned_candidate_available"] = bool(cleaned_candidate)
        props["cleaned_candidate_geometry"] = cleaned_candidate
        props["cleaned_candidate_reason"] = (
            "candidate geometry removes only label-mask, white-background, and hatch-grid hole artifacts and is review-only"
            if cleaned_candidate
            else "no geometry candidate generated; current evidence is diagnostic only"
        )
        props["spike_fixed_count"] = 0
        props["spike_review_required_count"] = 1 if "needle_spike_candidate" in flags else 0
        props["sliver_removed_count"] = 0
        props["thin_corridor_removed_count"] = 0
        if flags:
            artifact_review_count += 1
            props["classification_status"] = "artifact_requires_review"
            props["export_blocking_reason"] = "Blocked: geometry artifact candidate requires human review before export"
        elif legend_item and legend_item.get("missing_expected_symbol_count"):
            props["classification_status"] = "requires_review"
            props["export_blocking_reason"] = f"Blocked: matched legend item {target_code} is missing STAV/NAVRH symbol confirmation"
        elif target_code:
            props["classification_status"] = "requires_review"
            props["export_blocking_reason"] = f"Blocked: proposed mapping {target_code} needs explicit human approval"
        else:
            props["classification_status"] = "requires_review"
            props["export_blocking_reason"] = "Blocked: no legend match or proposal evidence available"
        props["artifact_flags"] = sorted(set(flags))
        props["export_eligible"] = False
    return {
        "algorithm": "selected_polygon_proposal_annotation_v1",
        "feature_proposal_count": proposal_count,
        "unmapped_feature_count": unmapped_count,
        "artifact_requires_review_feature_count": artifact_review_count,
    }


def build_visual_artifact_diagnostics(
    raw_features: list[dict[str, Any]],
    primary_features: list[dict[str, Any]],
) -> dict[str, Any]:
    white_raw = [
        feature
        for feature in raw_features
        if is_near_white(str((feature.get("properties") or {}).get("source_style_hex") or ""))
    ]
    background_raw = [
        feature
        for feature in raw_features
        if (feature.get("properties") or {}).get("fragment_role") == "background_mask_fragment"
    ]
    primary_metrics = [feature_shape_metrics(feature) for feature in primary_features]
    hole_cleanup_rows = [(feature.get("properties") or {}).get("hole_cleanup") or {} for feature in primary_features]
    hole_type_counts: Counter[str] = Counter()
    for feature in primary_features:
        hole_type_counts.update((feature.get("properties") or {}).get("hole_type_counts") or {})
    max_spike = max((row["spike_score"] for row in primary_metrics), default=0.0)
    spike_review_count = sum(1 for feature in primary_features if "artifact_requires_review" in ((feature.get("properties") or {}).get("artifact_flags") or []))
    trusted_white = [
        feature
        for feature in primary_features
        if is_near_white(str((feature.get("properties") or {}).get("source_style_hex") or ""))
    ]
    return {
        "algorithm": "visual_artifact_diagnostics_v1",
        "geometry_cleanup_algorithm": "geometry_artifact_review_flagging_v1+review_candidate_remove_label_mask_white_background_hatch_grid_holes_v8_2",
        "geometry_cleanup_tolerance": 0.0,
        "geometry_cleanup_reason": "V8.2 keeps raw/staging geometries immutable; label-mask, white-background, and hatch-grid holes may get a separate review-only cleaned candidate, never silent export.",
        "white_fill_fragment_count": len(white_raw),
        "white_fill_fragment_area": round(sum(geometry_area(feature.get("geometry") or {}) for feature in white_raw), 3),
        "background_mask_candidate_count": len(background_raw),
        "trusted_white_or_background_feature_count": len(trusted_white),
        **geometry_hole_metrics(primary_features),
        "max_spike_score": round(max_spike, 4),
        "spike_count": sum(1 for row in primary_metrics if row["spike_score"] >= 0.55),
        "spike_fixed_count": 0,
        "spike_review_required_count": sum(1 for feature in primary_features if "needle_spike_candidate" in ((feature.get("properties") or {}).get("artifact_flags") or [])),
        "needle_count": sum(int(row["needle_count"]) for row in primary_metrics),
        "sliver_component_count": sum(int(row["sliver_component_count"]) for row in primary_metrics),
        "thin_corridor_count": sum(int(row["thin_corridor_count"]) for row in primary_metrics),
        "sliver_removed_count": 0,
        "thin_corridor_removed_count": 0,
        "cleaned_candidate_feature_count": sum(1 for feature in primary_features if (feature.get("properties") or {}).get("cleaned_candidate_available")),
        "hole_type_counts": dict(hole_type_counts),
        "hole_cleanup_candidate_feature_count": sum(1 for row in hole_cleanup_rows if row.get("applied_to_candidate")),
        "hole_cleanup_removed_hole_count": sum(int(row.get("removed_hole_count") or 0) for row in hole_cleanup_rows),
        "hole_cleanup_review_required_hole_count": sum(int(row.get("review_required_hole_count") or 0) for row in hole_cleanup_rows),
        "export_blocked_feature_count": sum(1 for feature in primary_features if not (feature.get("properties") or {}).get("export_eligible")),
        "artifact_requires_review_feature_count": spike_review_count,
    }


def build_up_extraction_profile(
    *,
    pdf_name: str | None,
    raw_features: list[dict[str, Any]],
    primary_features: list[dict[str, Any]],
    text_specs: list[dict[str, Any]],
    legend_detection: dict[str, Any],
    artifact_diagnostics: dict[str, Any],
) -> dict[str, Any]:
    raw_count = max(len(raw_features), 1)
    white_line_candidates = []
    black_dot_candidates = []
    thick_boundary_candidates = []
    for feature in raw_features:
        props = feature.get("properties") or {}
        bbox = feature_bbox(feature)
        area = geometry_area(feature.get("geometry") or {})
        width = max(0.0, bbox[2] - bbox[0]) if bbox else 0.0
        height = max(0.0, bbox[3] - bbox[1]) if bbox else 0.0
        stroke = str(props.get("source_stroke_hex") or "")
        fill = str(props.get("source_fill_hex") or props.get("source_style_hex") or "")
        stroke_width = float(props.get("stroke_width") or 0.0)
        if is_near_white(stroke) or is_near_white(fill):
            if area <= 250.0 or min(width, height) <= 4.0:
                white_line_candidates.append(feature)
        if (is_near_black(stroke) or is_near_black(fill)) and area <= 180.0 and max(width, height) <= 20.0:
            black_dot_candidates.append(feature)
        if (is_near_black(stroke) or is_near_black(fill)) and (stroke_width >= 1.8 or min(width, height) <= 3.0) and area <= 1200.0:
            thick_boundary_candidates.append(feature)

    target_labels = [
        row
        for row in text_specs
        if row.get("matched_code_candidate") or str(row.get("raw_text") or "").strip().startswith(("Z.", "P.", "K."))
    ]
    hatch_hole_artifact_count = int(((artifact_diagnostics.get("hole_type_counts") or {}).get("hatch_grid_artifact")) or 0)
    hatch_candidate_count = len(white_line_candidates) + hatch_hole_artifact_count
    export_blocked_count = int(artifact_diagnostics.get("export_blocked_feature_count") or 0)
    manual_split_required = bool(hatch_candidate_count or black_dot_candidates or thick_boundary_candidates)
    manual_split_features = [
        feature
        for feature in primary_features
        if (feature.get("properties") or {}).get("source_text_nearby")
        or (feature.get("properties") or {}).get("proposed_CLASS") != "UNMAPPED"
    ] if manual_split_required else []

    methods = [
        {
            "method": "fill_style_polygonization",
            "czech_explanation": "Bere uzavřené plochy podle barvy výplně z PDF vektorů.",
            "status": "used" if primary_features else "failed",
            "success_rate": round(len(primary_features) / raw_count, 4) if raw_features else None,
            "used_for_candidate": True,
            "main_evidence": f"{len(primary_features)} kandidátních polygonů z {len(raw_features)} vektorových objektů",
            "main_risk": "Stejná výplň může spojit šrafované i nešrafované oblasti.",
        },
        {
            "method": "hatch_pattern_segmentation",
            "czech_explanation": "Hledá šrafování/mřížku uvnitř plochy a zkouší ji oddělit jako samostatnou oblast.",
            "status": "manual_required" if hatch_candidate_count else "not_attempted",
            "success_rate": None,
            "used_for_candidate": False,
            "main_evidence": f"{len(white_line_candidates)} bílých tenkých čar; {hatch_hole_artifact_count} hatch-grid hole artifacts po sloučení",
            "main_risk": "Vektorové šrafy zatím nejsou spolehlivě izolované od ostatních bílých masek.",
        },
        {
            "method": "dotted_boundary_segmentation",
            "czech_explanation": "Hledá tečkovanou nebo silnou hranici, která vymezuje změnovou plochu.",
            "status": "manual_required" if black_dot_candidates else "not_attempted",
            "success_rate": None,
            "used_for_candidate": False,
            "main_evidence": f"{len(black_dot_candidates)} malých tmavých/dot hranic",
            "main_risk": "Tečky mohou být hranice, značky parcel nebo textové grafické prvky.",
        },
        {
            "method": "thick_line_boundary_segmentation",
            "czech_explanation": "Hledá silné hranice, které mohou rozdělovat plánovací plochy.",
            "status": "review_required" if thick_boundary_candidates else "not_attempted",
            "success_rate": None,
            "used_for_candidate": False,
            "main_evidence": f"{len(thick_boundary_candidates)} silných/tmavých hranových kandidátů",
            "main_risk": "Bez uzavření hranice hrozí špatné rozdělení plochy.",
        },
        {
            "method": "text_anchor_region_assignment",
            "czech_explanation": "Přiřazuje popisky jako BX.p nebo Z.51a k nejbližší/obsahující ploše.",
            "status": "used" if target_labels else "not_attempted",
            "success_rate": None,
            "used_for_candidate": bool(target_labels),
            "main_evidence": f"{len(target_labels)} textových kotev",
            "main_risk": "Popisek sám nerozděluje geometrii a může jen potvrdit ruční split.",
        },
        {
            "method": "legend_style_mapping",
            "czech_explanation": "Mapuje barvy a symboly z legendy na třídy ploch.",
            "status": "used" if legend_detection.get("bbox") else "review_required",
            "success_rate": legend_detection.get("confidence"),
            "used_for_candidate": bool(legend_detection.get("bbox")),
            "main_evidence": f"{len(legend_detection.get('legend_candidates') or [])} kandidátů legendy",
            "main_risk": "Legenda nerozděluje vnitřní šrafované části bez geometrické hranice.",
        },
        {
            "method": "raster_assisted_segmentation",
            "czech_explanation": "Porovnává vektorovou extrakci s vykresleným obrázkem PDF stránky.",
            "status": "attempted",
            "success_rate": None,
            "used_for_candidate": False,
            "main_evidence": "Vykreslený plán slouží jako vizuální kontrola.",
            "main_risk": "Raster je zatím pouze podpůrný důkaz, ne zdroj automatického splitu.",
        },
        {
            "method": "manual_split_required",
            "czech_explanation": "Automatika nestačí, plocha musí být ručně rozdělená nebo potvrzená.",
            "status": "manual_required" if manual_split_required or export_blocked_count else "not_attempted",
            "success_rate": None,
            "used_for_candidate": False,
            "main_evidence": f"{export_blocked_count} export-blocked polygonů; {len(manual_split_features)} polygonů s textovou/třídní kotvou; hatch/dot kandidáti: {hatch_candidate_count}/{len(black_dot_candidates)}",
            "main_risk": "Export bez ručního splitu by spojil oblasti s odlišnou plánovací semantikou.",
        },
    ]
    attempted = [row["method"] for row in methods if row["status"] != "not_attempted"]
    used = [row["method"] for row in methods if row["used_for_candidate"]]
    rejected = [
        {"method": row["method"], "reason": row["main_risk"]}
        for row in methods
        if row["status"] in {"review_required", "manual_required", "failed"} and not row["used_for_candidate"]
    ]
    return {
        "pdf_name": pdf_name,
        "algorithm": "method_aware_extraction_profile_v8_2",
        "methods_attempted": attempted,
        "methods_used_for_candidate": used,
        "methods_rejected": rejected,
        "method_rows": methods,
        "overall_confidence": "review_required" if export_blocked_count or manual_split_required else "candidate",
        "export_status": "blocked" if export_blocked_count or manual_split_required else "review_required",
        "manual_split_required_count": len(manual_split_features),
        "manual_split_feature_ids_sample": [
            (feature.get("properties") or {}).get("FID", feature.get("id"))
            for feature in manual_split_features[:30]
        ],
        "hatch_candidate_count": hatch_candidate_count,
        "white_line_hatch_candidate_count": len(white_line_candidates),
        "hatch_hole_artifact_count": hatch_hole_artifact_count,
        "dotted_boundary_candidate_count": len(black_dot_candidates),
        "thick_boundary_candidate_count": len(thick_boundary_candidates),
        "text_anchor_count": len(target_labels),
        "export_blocked_feature_count": export_blocked_count,
    }


def attach_method_profile_to_features(features: list[dict[str, Any]], profile: dict[str, Any]) -> None:
    manual_required = int(profile.get("manual_split_required_count") or 0) > 0
    for feature in features:
        props = feature.setdefault("properties", {})
        props["up_extraction_methods_attempted"] = profile.get("methods_attempted", [])
        props["up_extraction_methods_used"] = profile.get("methods_used_for_candidate", [])
        props["manual_split_required"] = bool(manual_required and (props.get("source_text_nearby") or props.get("proposed_CLASS") != "UNMAPPED"))
        props["manual_split_reason"] = (
            "hatch/dotted/thick boundary candidates were detected, but automatic semantic split is not reliable enough for export"
            if props["manual_split_required"]
            else None
        )
        if props["manual_split_required"]:
            props["export_blocking_reason"] = "Blocked: manual split required for hatch/dotted-boundary semantic separation"
            props["export_eligible"] = False


def _round_ring(points: Iterable[Any]) -> list[list[float]]:
    return [[round(float(x), 3), round(float(y), 3)] for x, y in points]


def _shapely_polygon_to_geojson_coordinates(polygon: Any) -> list[list[list[float]]]:
    exterior = _round_ring(polygon.exterior.coords)
    interiors = [_round_ring(ring.coords) for ring in polygon.interiors if len(ring.coords) >= 4]
    return [exterior, *interiors]


def merge_tessellated_fill_features(
    features: list[dict[str, Any]],
    *,
    run_id: str,
    collection_id: str,
    source_url: str | None,
    source_pdf: str | None,
    source_fingerprint: str,
    page_number: int,
    tessellation: dict[str, Any],
    min_group_size: int = 2,
    min_component_area: float = 10.0,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    if not tessellation.get("tessellated_fill_detected"):
        return features, {
            "merge_algorithm": "vector_tessellated_fill_merge_v1",
            "merge_skipped_reason": "tessellation_not_detected",
            "raw_fragment_count": len(features),
            "merged_polygon_count": len(features),
            "raw_features_are_debug_only": False,
        }, []
    if unary_union is None or Polygon is None:
        return features, {
            "merge_algorithm": "vector_tessellated_fill_merge_v1",
            "merge_skipped_reason": "shapely_unavailable",
            "raw_fragment_count": len(features),
            "merged_polygon_count": len(features),
            "raw_features_are_debug_only": False,
        }, [
            {
                "error_code": "tessellated_merge_dependency_missing",
                "message": "Shapely is required for vector_tessellated_fill_merge_v1",
            }
        ]

    start = time.perf_counter()
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    skipped_non_map = 0
    skipped_by_role: Counter[str] = Counter()
    for feature in features:
        props = feature.get("properties") or {}
        if props.get("source_region_class") != "map_body_region":
            skipped_non_map += 1
            continue
        role = props.get("fragment_role")
        if role and role not in {"area_fill_candidate", "tessellated_area_fragment"}:
            skipped_by_role[str(role)] += 1
            continue
        key = (
            props.get("source_style_hex"),
            props.get("source_fill_opacity"),
            props.get("source_stroke_hex"),
            props.get("source_stroke_opacity"),
            props.get("stroke_width"),
            props.get("dash_pattern_normalized") or "solid",
            props.get("source_layer_name"),
        )
        groups[key].append(feature)

    merged_features: list[dict[str, Any]] = []
    group_stats: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    fid = 1
    for group_index, (key, group_features) in enumerate(sorted(groups.items(), key=lambda item: len(item[1]), reverse=True), 1):
        if len(group_features) < min_group_size:
            continue
        polygons = []
        invalid_count = 0
        for feature in group_features:
            polygon = _feature_to_shapely_polygon(feature)
            if polygon is None:
                invalid_count += 1
                continue
            polygons.extend(_polygon_geometries_from_shape(polygon))
        if not polygons:
            continue
        group_start = time.perf_counter()
        try:
            unioned = unary_union(polygons)
        except Exception as exc:
            repaired = []
            for polygon in polygons:
                try:
                    repaired.append(polygon.buffer(0))
                except Exception:
                    invalid_count += 1
            try:
                unioned = unary_union(repaired)
            except Exception as retry_exc:
                errors.append(
                    {
                        "error_code": "tessellated_group_merge_failed",
                        "message": f"{type(retry_exc).__name__}: {retry_exc}",
                        "group_index": group_index,
                        "source_style_hex": key[0],
                        "source_fragment_count": len(group_features),
                        "initial_exception": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
        components = [
            polygon
            for polygon in _polygon_geometries_from_shape(unioned)
            if not polygon.is_empty and polygon.area >= min_component_area
        ]
        source_area_sum = sum(geometry_area(feature.get("geometry") or {}) for feature in group_features)
        group_id = f"merged-group-{stable_hash(repr(key), 10)}"
        group_stats.append(
            {
                "merged_group_id": group_id,
                "source_style_hex": key[0],
                "source_fill_opacity": key[1],
                "source_stroke_hex": key[2],
                "source_stroke_opacity": key[3],
                "stroke_width": key[4],
                "dash_pattern_normalized": key[5],
                "source_layer_name": key[6],
                "source_fragment_count": len(group_features),
                "invalid_fragment_count": invalid_count,
                "merged_component_count": len(components),
                "source_fragment_area_sum": round(source_area_sum, 3),
                "merged_area_page_pt2": round(sum(component.area for component in components), 3),
                "runtime_ms": round((time.perf_counter() - group_start) * 1000),
            }
        )
        sample_ids = [str(feature.get("id")) for feature in group_features[:12]]
        sample_drawing_indexes = [
            (feature.get("properties") or {}).get("source_drawing_index")
            for feature in group_features[:12]
        ]
        for component_index, polygon in enumerate(components, 1):
            coords = _shapely_polygon_to_geojson_coordinates(polygon)
            bbox = [round(value, 3) for value in polygon.bounds]
            props = {
                "FID": fid,
                "up_id": None,
                "up_type_id": None,
                "LAYER": "UNCLASSIFIED",
                "CLASS": "UNMAPPED",
                "TYPE": "UNMAPPED",
                "LAYER_CLASS": "UNCLASSIFIED.UNMAPPED",
                "class_type": "UNMAPPED.0",
                "text_id": None,
                "IS_CLOSED": True,
                "source_style_hex": key[0],
                "source_fill_hex": key[0],
                "source_fill_opacity": key[1],
                "source_stroke_hex": key[2],
                "source_stroke_opacity": key[3],
                "source_style_group_id": group_id,
                "source_vector_def_id": None,
                "source_layer_name": key[6],
                "source_region_class": "map_body_region",
                "source_url": source_url,
                "source_pdf": source_pdf,
                "source_pdf_sha256": source_fingerprint,
                "page": page_number,
                "bbox_page_pt": bbox,
                "component_area_page_pt2": round(float(polygon.area), 3),
                "classification_status": "candidate_requires_legend_or_profile_mapping",
                "is_merged_candidate": True,
                "merged_group_id": group_id,
                "merged_component_index": component_index,
                "source_fragment_count": len(group_features),
                "raw_fragment_ids_sample": sample_ids,
                "source_drawing_index_sample": sample_drawing_indexes,
                "source_fragment_area_sum": round(source_area_sum, 3),
                "merged_area_page_pt2": round(float(polygon.area), 3),
                "merge_algorithm": "vector_tessellated_fill_merge_v1",
                "merge_tolerance": 0.0,
                "primary_display_mode": "merged_polygons",
                "display_fill_hex": key[0] or CLASS_DISPLAY_COLORS["UNMAPPED"],
                "display_stroke_hex": key[2] or "#222222",
                "display_color_source": "source_style" if key[0] else "fallback_unmapped",
            }
            merged_features.append(
                {
                    "type": "Feature",
                    "id": f"merged-{fid:05d}",
                    "properties": props,
                    "geometry": {"type": "Polygon", "coordinates": coords},
                }
            )
            fid += 1

    stats = {
        "merge_algorithm": "vector_tessellated_fill_merge_v1",
        "merge_strategy": "shapely_unary_union_by_style_map_body_v1",
        "raw_fragment_count": len(features),
        "raw_map_body_fragment_count": sum(len(group) for group in groups.values()),
        "raw_non_map_fragment_count": skipped_non_map,
        "raw_skipped_by_fragment_role": dict(skipped_by_role),
        "merged_group_count": len(group_stats),
        "merged_polygon_count": len(merged_features),
        "merged_groups": group_stats[:80],
        "merge_error_count": len(errors),
        "merge_runtime_ms": round((time.perf_counter() - start) * 1000),
        "raw_features_are_debug_only": True,
        "primary_extraction_mode": "merged_polygons",
    }
    return merged_features, stats, errors


def associate_features_with_target_text(
    features: list[dict[str, Any]],
    text_specs: list[dict[str, Any]],
) -> dict[str, Any]:
    targets = [
        row
        for row in text_specs
        if row.get("matched_code_candidate") and row.get("bbox_page_pt")
    ]
    assigned = 0
    for feature in features:
        bbox = feature_bbox(feature)
        if not bbox:
            continue
        expanded = [bbox[0] - 18.0, bbox[1] - 18.0, bbox[2] + 18.0, bbox[3] + 18.0]
        best: tuple[float, dict[str, Any]] | None = None
        center = bbox_center(bbox)
        for text in targets:
            text_center = bbox_center(text.get("bbox_page_pt"))
            if not text_center:
                continue
            inside = bbox_contains_point(expanded, text_center)
            distance = (
                ((center[0] - text_center[0]) ** 2 + (center[1] - text_center[1]) ** 2) ** 0.5
                if center
                else 0.0
            )
            if inside or distance <= 35.0:
                score = 0.0 if inside else distance
                if best is None or score < best[0]:
                    best = (score, text)
        if best:
            text = best[1]
            props = feature.setdefault("properties", {})
            props["source_text_nearby"] = text.get("raw_text")
            props["matched_text_def_id"] = text.get("text_def_id")
            props["target_code_candidate"] = text.get("matched_code_candidate")
            assigned += 1
    return {
        "target_text_count": len(targets),
        "feature_text_association_count": assigned,
        "association_algorithm": "bbox_contains_or_nearest_target_text_v1",
    }


def detect_source(
    *,
    source_filename: str | None,
    source_url: str | None,
    page_count: int,
    drawing_count: int,
    image_count: int,
    text_count: int,
) -> dict[str, Any]:
    has_vector = drawing_count > 0
    has_images = image_count > 0
    has_text = text_count > 0
    if has_vector and has_images:
        source_type = "mixed_pdf"
        confidence = 0.88
        reason = "PDF has vector drawings and images"
    elif has_vector:
        source_type = "vector_pdf"
        confidence = 0.92
        reason = "PDF has vector drawing objects"
    elif has_images:
        source_type = "raster_pdf"
        confidence = 0.82
        reason = "PDF has images but no vector drawings"
    else:
        source_type = "unsupported_pdf"
        confidence = 0.35
        reason = "PDF has no usable vector drawings or images"
    return {
        "source_type": source_type,
        "source_filename": source_filename,
        "source_url": source_url,
        "detection_algorithm": "pdf_drawings_images_text_v1",
        "page_count": page_count,
        "drawing_count": drawing_count,
        "image_count": image_count,
        "text_span_count": text_count,
        "has_vector_drawings": has_vector,
        "has_images": has_images,
        "has_text": has_text,
        "is_probably_scanned": has_images and not has_vector and not has_text,
        "is_mixed_pdf": has_vector and has_images,
        "confidence": confidence,
        "reason": reason,
        "warnings": [] if source_type in {"vector_pdf", "mixed_pdf"} else ["No trusted vector area extraction available for this source type"],
    }


def detection_for_geojson(*, source_filename: str | None, source_url: str | None, feature_count: int) -> dict[str, Any]:
    return {
        "source_type": "geojson",
        "source_filename": source_filename,
        "source_url": source_url,
        "detection_algorithm": "json_feature_collection_v1",
        "page_count": None,
        "drawing_count": 0,
        "image_count": 0,
        "text_span_count": 0,
        "has_vector_drawings": False,
        "has_images": False,
        "has_text": False,
        "is_probably_scanned": False,
        "is_mixed_pdf": False,
        "confidence": 0.98,
        "reason": f"GeoJSON FeatureCollection with {feature_count} features",
        "warnings": [],
    }


def structured_error(
    *,
    run_id: str,
    collection_id: str,
    source_url: str | None,
    source_filename: str | None,
    source_fingerprint: str | None,
    step: str,
    algorithm: str,
    severity: str,
    error_code: str,
    message: str,
    exc: BaseException | None = None,
    recovery_action: str = "requires_review",
    retryable: bool = False,
    affected_page_number: int | None = None,
    affected_feature_id: str | None = None,
    affected_vector_def_id: str | None = None,
    affected_text_def_id: str | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "collection_id": collection_id,
        "source_url": source_url,
        "source_filename": source_filename,
        "source_fingerprint": source_fingerprint,
        "step": step,
        "algorithm": algorithm,
        "severity": severity,
        "error_code": error_code,
        "message": message,
        "exception_type": type(exc).__name__ if exc else None,
        "traceback_summary": "".join(traceback.format_exception_only(type(exc), exc)).strip() if exc else None,
        "timestamp": now_iso(),
        "affected_page_number": affected_page_number,
        "affected_feature_id": affected_feature_id,
        "affected_vector_def_id": affected_vector_def_id,
        "affected_text_def_id": affected_text_def_id,
        "recovery_action": recovery_action,
        "retryable": retryable,
    }


def pipeline_step(
    *,
    run_id: str,
    collection_id: str,
    step_order: int,
    step_name: str,
    algorithm: str,
    input_count: int,
    output_count: int,
    skipped_count: int = 0,
    rejected_count: int = 0,
    warning_count: int = 0,
    error_count: int = 0,
    runtime_ms: int = 0,
    status: str = "ok",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "collection_id": collection_id,
        "step_order": step_order,
        "step_name": step_name,
        "algorithm": algorithm,
        "input_count": input_count,
        "output_count": output_count,
        "skipped_count": skipped_count,
        "rejected_count": rejected_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "runtime_ms": runtime_ms,
        "status": status,
        "details": details or {},
    }


def classify_evidence(
    *,
    raw_layer: str | None,
    raw_class: str | None,
    raw_type: str | None,
    source_fill_hex: str | None = None,
    source_stroke_hex: str | None = None,
    stroke_width: float | None = None,
    dash_pattern_normalized: str | None = None,
    source_layer_name: str | None = None,
    source_text_nearby: str | None = None,
    legend_label_candidate: str | None = None,
    legend_crop_id: str | None = None,
) -> dict[str, Any]:
    evidence: list[tuple[str, str, str, float]] = []
    for evidence_name, value, score in [
        ("existing_class", raw_class, 0.92),
        ("source_layer_name", source_layer_name, 0.78),
        ("text_label", source_text_nearby, 0.86),
        ("legend_label", legend_label_candidate, 0.92),
    ]:
        code = detect_target_code(value)
        if code:
            evidence.append((evidence_name, code, TARGET_CODE_CLASSES[code], score))
        label_code, label_group = detect_target_label(value)
        if label_code and label_group:
            evidence.append((evidence_name, label_code, label_group, score - 0.04))

    groups = {group for _, _, group, _ in evidence}
    codes = {code for _, code, _, _ in evidence}
    has_dash = bool(dash_pattern_normalized and dash_pattern_normalized != "solid")
    base = {
        "raw_LAYER": raw_layer,
        "raw_CLASS": raw_class,
        "raw_TYPE": raw_type,
        "source_fill_hex": source_fill_hex,
        "source_stroke_hex": source_stroke_hex,
        "stroke_width": stroke_width,
        "dash_pattern_normalized": dash_pattern_normalized,
        "source_layer_name": source_layer_name,
        "source_text_nearby": source_text_nearby,
        "legend_label_candidate": legend_label_candidate,
        "legend_crop_id": legend_crop_id,
        "evidence_vector_style": bool(source_fill_hex or source_stroke_hex),
        "evidence_dash_pattern": has_dash,
        "evidence_text_label": bool(source_text_nearby),
        "evidence_legend_crop": bool(legend_crop_id),
        "evidence_source_layer_name": bool(source_layer_name),
    }
    if not evidence:
        return {
            **base,
            "proposed_up_layer": "UNMAPPED",
            "proposed_up_class": "UNMAPPED",
            "proposed_up_type": raw_type or "UNMAPPED",
            "is_inscope_bydleni_related": False,
            "confidence": 0.12 if base["evidence_vector_style"] else 0.0,
            "rule_id": "unknown_requires_review",
            "rule_reason": "no code, text, source layer, or legend evidence matched target scope",
            "requires_review": True,
            "reviewer_decision": None,
            "final_up_layer": None,
            "final_up_class": None,
            "final_up_type": None,
        }
    if len(groups) > 1 or len(codes) > 1:
        return {
            **base,
            "proposed_up_layer": "UNMAPPED",
            "proposed_up_class": "UNMAPPED",
            "proposed_up_type": raw_type or "UNMAPPED",
            "is_inscope_bydleni_related": True,
            "confidence": 0.24,
            "rule_id": "conflicting_target_evidence",
            "rule_reason": "multiple target classes/groups matched; operator review required",
            "requires_review": True,
            "reviewer_decision": None,
            "final_up_layer": None,
            "final_up_class": None,
            "final_up_type": None,
        }
    best = max(evidence, key=lambda item: item[3])
    evidence_name, code, group, score = best
    confidence = max(0.0, min(0.98, score - (0.18 if has_dash else 0.0)))
    requires_review = has_dash or evidence_name in {"existing_class", "source_layer_name"} and not (source_text_nearby or legend_label_candidate)
    return {
        **base,
        "proposed_up_layer": "RZVP",
        "proposed_up_class": code,
        "proposed_up_type": raw_type or "UNMAPPED",
        "is_inscope_bydleni_related": True,
        "confidence": round(confidence, 3),
        "rule_id": f"{evidence_name}_target_scope_match",
        "rule_reason": f"{evidence_name} matched target group {group}; dash pattern lowers confidence" if has_dash else f"{evidence_name} matched target group {group}",
        "requires_review": requires_review,
        "reviewer_decision": None,
        "final_up_layer": None if requires_review else "RZVP",
        "final_up_class": None if requires_review else code,
        "final_up_type": None if requires_review else raw_type,
    }


def extract_text_specs(
    *,
    page: Any,
    run_id: str,
    collection_id: str,
    source_pdf: str | None,
    source_fingerprint: str,
    page_number: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    specs: list[dict[str, Any]] = []
    definitions: dict[tuple[Any, ...], dict[str, Any]] = {}
    try:
        blocks = page.get_text("dict").get("blocks", [])
    except Exception:
        blocks = []
    for block_index, block in enumerate(blocks):
        for line_index, line in enumerate(block.get("lines", [])):
            spans = line.get("spans", [])
            for span_index, span in enumerate(spans):
                raw_text = str(span.get("text") or "").strip()
                if not raw_text:
                    continue
                norm = normalized_text(raw_text)
                code = detect_target_code(raw_text)
                label_code, _label_group = detect_target_label(raw_text)
                bbox = [float(value) for value in span.get("bbox", [])] if span.get("bbox") else None
                text_def_id = f"text-def-{len(specs) + 1:04d}"
                spec = {
                    "text_def_id": text_def_id,
                    "run_id": run_id,
                    "collection_id": collection_id,
                    "source_pdf": source_pdf,
                    "source_fingerprint": source_fingerprint,
                    "page_number": page_number,
                    "text_block_index": block_index,
                    "text_line_index": line_index,
                    "text_span_index": span_index,
                    "raw_text": raw_text,
                    "normalized_text": norm,
                    "language_hint": "cs",
                    "font_name": span.get("font"),
                    "font_family": str(span.get("font") or "").split("-")[0] or None,
                    "font_size": span.get("size"),
                    "font_weight_hint": "bold" if "bold" in fold_text(span.get("font")) else None,
                    "is_bold_hint": "bold" in fold_text(span.get("font")),
                    "is_italic_hint": "italic" in fold_text(span.get("font")) or "oblique" in fold_text(span.get("font")),
                    "text_color_rgb": span.get("color"),
                    "text_color_hex": rgb_to_hex(span.get("color")),
                    "text_opacity": span.get("alpha"),
                    "bbox_page_pt": bbox,
                    "baseline_start_pt": None,
                    "baseline_end_pt": None,
                    "rotation_degrees": None,
                    "writing_direction": line.get("dir"),
                    "char_count": len(raw_text),
                    "token_count": len(raw_text.split()),
                    "nearby_vector_def_ids": [],
                    "nearby_feature_ids": [],
                    "legend_candidate_score": 0.82 if (code or label_code) else 0.0,
                    "classification_candidate_score": 0.9 if (code or label_code) else 0.0,
                    "matched_code_candidate": code or label_code,
                    "matched_label_candidate": raw_text if label_code else None,
                    "rejected_reason": None if (code or label_code) else "not_target_scope_text",
                }
                specs.append(spec)
                key = (norm, spec["font_name"], spec["text_color_hex"])
                if key not in definitions:
                    definitions[key] = {
                        **spec,
                        "candidate_id": text_def_id,
                        "sample_text": raw_text,
                        "sample_count": 1,
                        "text_role": "classification_or_legend_candidate" if (code or label_code) else "source_text",
                    "regex_pattern": r"^(B|BI|BV|BH|BU|BX\.[cpr]|R|RI|RX|S|SO|SV|SC|SX)$",
                        "association_strategy": "text_span_inventory_nearby_assignment_pending",
                        "candidate_status": "candidate" if (code or label_code) else "requires_review",
                    }
                else:
                    definitions[key]["sample_count"] += 1
    return specs, list(definitions.values())


def build_vector_records(
    *,
    drawings: list[dict[str, Any]],
    features: list[dict[str, Any]],
    run_id: str,
    collection_id: str,
    source_pdf: str | None,
    source_fingerprint: str,
    page_number: int,
    algorithm: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    feature_ids_by_drawing: dict[int, list[str]] = {}
    areas_by_drawing: dict[int, float] = {}
    holes_by_drawing: dict[int, int] = {}
    for feature in features:
        props = feature.get("properties") or {}
        drawing_index = props.get("source_drawing_index")
        if drawing_index is None:
            continue
        feature_ids_by_drawing.setdefault(int(drawing_index), []).append(str(feature.get("id")))
        geom = feature.get("geometry") or {}
        areas_by_drawing[int(drawing_index)] = areas_by_drawing.get(int(drawing_index), 0.0) + geometry_area(geom)
        holes_by_drawing[int(drawing_index)] = holes_by_drawing.get(int(drawing_index), 0) + max(0, len(geom.get("coordinates") or []) - 1)

    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    traces: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    geometry_errors: list[dict[str, Any]] = []

    for drawing_index, draw in enumerate(drawings):
        items = draw.get("items", [])
        counts = path_item_type_counts(items)
        fill_hex = rgb_to_hex(draw.get("fill"))
        stroke_hex = rgb_to_hex(draw.get("color"))
        dash_array, dash_phase, dash_normalized = parse_dash_pattern(draw.get("dashes"))
        emitted = feature_ids_by_drawing.get(drawing_index, [])
        bbox = rect_bbox(draw.get("rect"))
        rejected_reason = None
        if fill_hex and not emitted:
            rejected_reason = "polygonization_failed_or_degenerate_ring"
            geometry_error = {
                "geometry_error_id": f"geom-error-{len(geometry_errors) + 1:04d}",
                "run_id": run_id,
                "collection_id": collection_id,
                "source_pdf": source_pdf,
                "source_fingerprint": source_fingerprint,
                "page_number": page_number,
                "error_type": "polygonization_failed",
                "drawing_index": drawing_index,
                "bbox_page_pt": bbox,
                "message": "filled drawing emitted no positive-area polygon",
                "trace_ref": f"vector-trace-{drawing_index:06d}",
                "review_status": "requires_review",
            }
            geometry_errors.append(geometry_error)
        key = (
            fill_hex,
            stroke_hex,
            draw.get("fill_opacity"),
            draw.get("stroke_opacity"),
            draw.get("width"),
            dash_normalized,
            draw.get("layer"),
            tuple(sorted(counts.items())),
            bool(fill_hex),
            bool(stroke_hex),
        )
        if key not in grouped:
            vector_def_id = f"vector-def-{len(grouped) + 1:04d}"
            grouped[key] = {
                "vector_def_id": vector_def_id,
                "candidate_id": vector_def_id,
                "run_id": run_id,
                "collection_id": collection_id,
                "source_pdf": source_pdf,
                "source_fingerprint": source_fingerprint,
                "page_number": page_number,
                "drawing_index": drawing_index,
                "drawing_group_id": stable_hash(repr(key), 12),
                "path_item_type_counts": counts,
                "has_l": counts.get("l", 0) > 0,
                "has_c": counts.get("c", 0) > 0,
                "has_qu": counts.get("qu", 0) > 0,
                "has_re": counts.get("re", 0) > 0,
                "has_close_path": bool(draw.get("closePath")),
                "is_closed_candidate": bool(fill_hex and emitted),
                "is_filled": bool(fill_hex),
                "is_stroked": bool(stroke_hex),
                "fill_color_rgb": draw.get("fill"),
                "fill_color_hex": fill_hex,
                "fill_hex": fill_hex,
                "fill_opacity": draw.get("fill_opacity"),
                "stroke_color_rgb": draw.get("color"),
                "stroke_color_hex": stroke_hex,
                "stroke_hex": stroke_hex,
                "stroke_opacity": draw.get("stroke_opacity"),
                "stroke_width": draw.get("width"),
                "stroke_line_cap": draw.get("lineCap"),
                "stroke_line_join": draw.get("lineJoin"),
                "stroke_miter_limit": None,
                "dash_pattern_raw": draw.get("dashes"),
                "dash_array": dash_array,
                "dash_phase": dash_phase,
                "dash_pattern_normalized": dash_normalized,
                "has_dash_pattern": bool(dash_normalized and dash_normalized != "solid"),
                "source_layer_name": draw.get("layer"),
                "source_ocg_name": None,
                "blend_mode": None,
                "even_odd_fill_rule": draw.get("even_odd"),
                "bbox_page_pt": bbox,
                "area_page_pt2": 0.0,
                "ring_count": 0,
                "hole_count": 0,
                "component_count": 0,
                "source_path_command_count": sum(counts.values()),
                "flattened_curve_segment_count": counts.get("c", 0) * 4,
                "simplification_tolerance": 0,
                "rejected_reason": rejected_reason,
                "emitted_feature_count": 0,
                "sample_feature_ids": [],
                "classification_status": "requires_review" if rejected_reason else "candidate_requires_legend_or_profile_mapping",
                "sample_count": 0,
                "candidate_status": "requires_review" if rejected_reason else "candidate",
            }
        group = grouped[key]
        group["sample_count"] += 1
        group["area_page_pt2"] += areas_by_drawing.get(drawing_index, 0.0)
        group["ring_count"] += len(emitted)
        group["hole_count"] += holes_by_drawing.get(drawing_index, 0)
        group["component_count"] += len(emitted)
        group["emitted_feature_count"] += len(emitted)
        group["sample_feature_ids"] = [*group["sample_feature_ids"], *emitted[:3]][:8]
        if rejected_reason and not group.get("rejected_reason"):
            group["rejected_reason"] = rejected_reason

        traces.append(
            {
                "trace_id": f"vector-trace-{drawing_index:06d}",
                "run_id": run_id,
                "collection_id": collection_id,
                "source_pdf": source_pdf,
                "source_fingerprint": source_fingerprint,
                "page_number": page_number,
                "algorithm": algorithm,
                "drawing_index": drawing_index,
                "path_item_type_counts": counts,
                "fill_color_hex": fill_hex,
                "stroke_color_hex": stroke_hex,
                "fill_opacity": draw.get("fill_opacity"),
                "stroke_opacity": draw.get("stroke_opacity"),
                "stroke_width": draw.get("width"),
                "dash_pattern_raw": draw.get("dashes"),
                "dash_array": dash_array,
                "dash_phase": dash_phase,
                "dash_pattern_normalized": dash_normalized,
                "has_dash_pattern": bool(dash_normalized and dash_normalized != "solid"),
                "source_layer_name": draw.get("layer"),
                "source_ocg_name": None,
                "is_closed_candidate": bool(fill_hex and emitted),
                "ring_count": len(emitted),
                "hole_count": holes_by_drawing.get(drawing_index, 0),
                "bbox_page_pt": bbox,
                "area_page_pt2": areas_by_drawing.get(drawing_index, 0.0),
                "rejected_reason": rejected_reason,
                "emitted_feature_id": emitted[0] if emitted else None,
                "classification_status": "requires_review" if rejected_reason else "candidate_requires_legend_or_profile_mapping",
            }
        )

    return list(grouped.values()), list(grouped.values()), traces, geometry_errors


def build_classification_proposals(
    *,
    vector_definitions: list[dict[str, Any]],
    text_definitions: list[dict[str, Any]],
    run_id: str,
    collection_id: str,
) -> list[dict[str, Any]]:
    target_text = next((row for row in text_definitions if row.get("matched_code_candidate") or row.get("matched_label_candidate")), None)
    proposals: list[dict[str, Any]] = []
    for index, vector_def in enumerate(vector_definitions, 1):
        text_value = target_text.get("raw_text") if target_text else None
        classified = classify_evidence(
            raw_layer=vector_def.get("candidate_layer"),
            raw_class=vector_def.get("candidate_class"),
            raw_type=vector_def.get("candidate_type"),
            source_fill_hex=vector_def.get("fill_color_hex") or vector_def.get("fill_hex"),
            source_stroke_hex=vector_def.get("stroke_color_hex") or vector_def.get("stroke_hex"),
            stroke_width=vector_def.get("stroke_width"),
            dash_pattern_normalized=vector_def.get("dash_pattern_normalized"),
            source_layer_name=vector_def.get("source_layer_name"),
            source_text_nearby=text_value,
            legend_label_candidate=vector_def.get("legend_label_text"),
            legend_crop_id=None,
        )
        proposals.append(
            {
                "classification_trace_id": f"classification-{index:04d}",
                "run_id": run_id,
                "collection_id": collection_id,
                "feature_id": (vector_def.get("sample_feature_ids") or [None])[0],
                "vector_def_id": vector_def.get("vector_def_id") or vector_def.get("candidate_id"),
                "text_def_id": target_text.get("text_def_id") if target_text else None,
                **classified,
            }
        )
    return proposals


def build_legend_crops(
    *,
    run_id: str,
    collection_id: str,
    source_pdf: str | None,
    source_fingerprint: str,
    text_definitions: list[dict[str, Any]],
    classification_proposals: list[dict[str, Any]],
    page: Any | None = None,
    legend_bbox: list[float] | None = None,
    legend_detection: dict[str, Any] | None = None,
    feature_region_stats: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    target_texts = [row for row in text_definitions if row.get("matched_code_candidate") or row.get("matched_label_candidate")]
    selected_candidate = next((row for row in (legend_detection or {}).get("legend_candidates", []) if row.get("selected")), {})
    artifact_path: str | None = None
    artifact_url: str | None = None
    image_width_px: int | None = None
    image_height_px: int | None = None
    transform: dict[str, float] | None = None
    if page is not None and legend_bbox:
        try:
            repo_root = Path(__file__).resolve().parents[2]
            out_dir = repo_root / "docs" / "legend_crops"
            out_dir.mkdir(parents=True, exist_ok=True)
            artifact = out_dir / f"{collection_id}_legend_0001.png"
            matrix = getattr(__import__("fitz"), "Matrix")(1.5, 1.5)
            rect = getattr(__import__("fitz"), "Rect")(*legend_bbox)
            pixmap = page.get_pixmap(matrix=matrix, clip=rect, alpha=False)
            image_width_px = int(pixmap.width)
            image_height_px = int(pixmap.height)
            transform = page_to_image_transform(legend_bbox, image_width_px, image_height_px)
            pixmap.save(str(artifact))
            artifact_path = str(artifact)
            artifact_url = f"/artifacts/legend_crops/{artifact.name}"
        except Exception:
            artifact_path = None
    if not target_texts:
        if artifact_path:
            return [
                {
                    "legend_crop_id": "legend-autocrop-0001",
                    "run_id": run_id,
                    "collection_id": collection_id,
                    "source_pdf": source_pdf,
                    "source_fingerprint": source_fingerprint,
                    "page_number": None,
                    "crop_bbox_page_pt": legend_bbox,
                    "legend_crop_source": "auto",
                    "legend_candidate_id": selected_candidate.get("candidate_id"),
                    "image_artifact_path": artifact_path,
                    "image_artifact_url": artifact_url,
                    "image_artifact_path_or_url": artifact_path,
                    "image_width_px": image_width_px,
                    "image_height_px": image_height_px,
                    "page_to_image_transform": transform,
                    **(transform or {}),
                    "extracted_text": None,
                    "matched_label": None,
                    "matched_code": None,
                    "matched_fill_hex": None,
                    "matched_stroke_hex": None,
                    "matched_dash_pattern": None,
                    "proposed_up_layer": None,
                    "proposed_up_class": None,
                    "proposed_up_type": None,
                    "anchor_type": (legend_detection or {}).get("strategy"),
                    "anchor_text": None,
                    "symbol_count_estimate": (feature_region_stats or {}).get("legend_candidate_feature_count", 0),
                    "target_code_count_estimate": (legend_detection or {}).get("target_code_count_estimate", 0),
                    "confidence": (legend_detection or {}).get("confidence", 0.0),
                    "review_status": "requires_review",
                    "unavailable_reason": "legend autocrop rendered, but text inventory found no target code/label candidate inside the PDF text layer",
                }
            ]
        return [
            {
                "legend_crop_id": "legend-unavailable-0001",
                "run_id": run_id,
                "collection_id": collection_id,
                "source_pdf": source_pdf,
                "source_fingerprint": source_fingerprint,
                "page_number": None,
                "crop_bbox_page_pt": None,
                "legend_crop_source": "unavailable",
                "image_artifact_path_or_url": None,
                "extracted_text": None,
                "matched_label": None,
                "matched_code": None,
                "matched_fill_hex": None,
                "matched_stroke_hex": None,
                "matched_dash_pattern": None,
                "proposed_up_layer": None,
                "proposed_up_class": None,
                "proposed_up_type": None,
                "confidence": 0.0,
                "review_status": "unavailable",
                "unavailable_reason": "legend crop detector not implemented for this source; text inventory found no target legend/code candidate",
            }
        ]
    crops: list[dict[str, Any]] = []
    if artifact_path:
        crop_target_texts = [
            row
            for row in target_texts
            if bbox_contains_point(legend_bbox, bbox_center(row.get("bbox_page_pt")))
        ]
        if not crop_target_texts:
            crop_target_texts = target_texts[:20]
        proposal = classification_proposals[0] if classification_proposals else {}
        crops.append(
            {
                "legend_crop_id": "legend-autocrop-0001",
                "run_id": run_id,
                "collection_id": collection_id,
                "source_pdf": source_pdf,
                "source_fingerprint": source_fingerprint,
                "page_number": crop_target_texts[0].get("page_number") if crop_target_texts else None,
                "crop_bbox_page_pt": legend_bbox,
                "legend_crop_source": "auto",
                "legend_candidate_id": selected_candidate.get("candidate_id"),
                "image_artifact_path": artifact_path,
                "image_artifact_url": artifact_url,
                "image_artifact_path_or_url": artifact_path,
                "image_width_px": image_width_px,
                "image_height_px": image_height_px,
                "page_to_image_transform": transform,
                **(transform or {}),
                "extracted_text": " ".join(str(row.get("raw_text") or "") for row in crop_target_texts[:24]).strip() or None,
                "matched_label": next((row.get("matched_label_candidate") for row in crop_target_texts if row.get("matched_label_candidate")), None),
                "matched_code": next((row.get("matched_code_candidate") for row in crop_target_texts if row.get("matched_code_candidate")), None),
                "matched_fill_hex": None,
                "matched_stroke_hex": None,
                "matched_dash_pattern": None,
                "proposed_up_layer": proposal.get("proposed_up_layer"),
                "proposed_up_class": proposal.get("proposed_up_class"),
                "proposed_up_type": proposal.get("proposed_up_type"),
                "anchor_type": (legend_detection or {}).get("strategy"),
                "anchor_text": crop_target_texts[0].get("raw_text") if crop_target_texts else None,
                "column_count_estimate": (legend_detection or {}).get("column_count_estimate", 1),
                "legend_column_count": (legend_detection or {}).get("column_count_estimate", 1),
                "legend_column_bboxes_page_pt": (legend_detection or {}).get("legend_column_bboxes_page_pt") or ([legend_bbox] if legend_bbox else []),
                "symbol_count_estimate": (feature_region_stats or {}).get("legend_candidate_feature_count", 0),
                "target_code_count_estimate": len({row.get("matched_code_candidate") for row in crop_target_texts if row.get("matched_code_candidate")}),
                "confidence": (legend_detection or {}).get("confidence", 0.0),
                "review_status": "requires_review",
                "unavailable_reason": None,
            }
        )
    for index, text_def in enumerate(target_texts[:20], 1):
        proposal = classification_proposals[0] if classification_proposals else {}
        crops.append(
            {
                "legend_crop_id": f"legend-text-anchor-{index:04d}",
                "run_id": run_id,
                "collection_id": collection_id,
                "source_pdf": source_pdf,
                "source_fingerprint": source_fingerprint,
                "page_number": text_def.get("page_number"),
                "crop_bbox_page_pt": text_def.get("bbox_page_pt"),
                "legend_crop_source": "text_anchor",
                "image_artifact_path_or_url": None,
                "extracted_text": text_def.get("raw_text"),
                "matched_label": text_def.get("matched_label_candidate"),
                "matched_code": text_def.get("matched_code_candidate"),
                "matched_fill_hex": None,
                "matched_stroke_hex": None,
                "matched_dash_pattern": None,
                "proposed_up_layer": proposal.get("proposed_up_layer"),
                "proposed_up_class": proposal.get("proposed_up_class"),
                "proposed_up_type": proposal.get("proposed_up_type"),
                "anchor_type": "target_text_anchor",
                "anchor_text": text_def.get("raw_text"),
                "symbol_count_estimate": None,
                "target_code_count_estimate": 1 if text_def.get("matched_code_candidate") else 0,
                "confidence": 0.4,
                "review_status": "requires_review",
                "unavailable_reason": None if artifact_path else "legend text candidate exists, but no rendered legend autocrop was available",
            }
        )
    return crops


def build_legend_rows(
    *,
    run_id: str,
    collection_id: str,
    source_pdf: str | None,
    source_fingerprint: str,
    text_specs: list[dict[str, Any]],
    legend_bbox: list[float] | None,
    legend_crops: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for spec in text_specs:
        code = spec.get("matched_code_candidate")
        if code:
            by_code[str(code)].append(spec)
    expected_codes = ["B", "BI", "BV", "BH", "BU", "BX.c", "BX.p", "BX.r", "R", "RI", "RX", "S", "SO", "SV", "SC", "SX"]
    crop_id = next((row.get("legend_crop_id") for row in legend_crops if row.get("image_artifact_path_or_url")), None)
    for index, code in enumerate(expected_codes, 1):
        specs = by_code.get(code, [])
        in_crop = [
            spec
            for spec in specs
            if legend_bbox and bbox_contains_point(legend_bbox, bbox_center(spec.get("bbox_page_pt")))
        ]
        anchor = in_crop[0] if in_crop else (specs[0] if specs else {})
        rows.append(
            {
                "legend_row_id": f"legend-row-{index:04d}",
                "run_id": run_id,
                "collection_id": collection_id,
                "source_pdf": source_pdf,
                "source_fingerprint": source_fingerprint,
                "legend_crop_id": crop_id,
                "target_code": code,
                "target_group": TARGET_CODE_CLASSES.get(code),
                "anchor_text": anchor.get("raw_text"),
                "anchor_text_def_id": anchor.get("text_def_id"),
                "anchor_bbox_page_pt": anchor.get("bbox_page_pt"),
                "anchor_in_autocrop": bool(in_crop),
                "map_text_occurrence_count": len(specs),
                "matched_fill_hex": None,
                "matched_stroke_hex": None,
                "matched_dash_pattern": None,
                "symbol_bbox_page_pt": None,
                "symbol_source": None,
                "confidence": 0.45 if in_crop else (0.28 if specs else 0.0),
                "review_status": "requires_review" if not in_crop else "candidate",
                "requires_review_reason": None if in_crop else "target code not confirmed inside the rendered legend autocrop",
            }
        )
    return rows


TARGET_LEGEND_CODES = ["BU", "BI", "BH", "BX.c", "BX.p", "BX.r", "RI", "SV", "SC", "SX"]


def expanded_bbox(bbox: list[float], dx: float, dy: float) -> list[float]:
    return [bbox[0] - dx, bbox[1] - dy, bbox[2] + dx, bbox[3] + dy]


def symbol_role_for_code_anchor(bbox: list[float], legend_bbox: list[float]) -> tuple[str, int]:
    center = bbox_center(bbox) or (bbox[0], bbox[1])
    rel_x = center[0] - legend_bbox[0]
    if rel_x < 130:
        return "stav_stabil", 1
    if rel_x < 230:
        return "navrh", 2
    return "ignored_extra", 3


def estimate_symbol_bbox(anchor_bbox: list[float], role: str, legend_bbox: list[float]) -> list[float]:
    center = bbox_center(anchor_bbox) or ((anchor_bbox[0] + anchor_bbox[2]) / 2, (anchor_bbox[1] + anchor_bbox[3]) / 2)
    if role == "stav_stabil":
        width = 86.0
    elif role == "navrh":
        width = 90.0
    else:
        width = 86.0
    bbox = [center[0] - width / 2, center[1] - 19.0, center[0] + width / 2, center[1] + 21.0]
    return [
        round(max(legend_bbox[0], bbox[0]), 3),
        round(max(legend_bbox[1], bbox[1]), 3),
        round(min(legend_bbox[2], bbox[2]), 3),
        round(min(legend_bbox[3], bbox[3]), 3),
    ]


def dominant_symbol_style(raw_features: list[dict[str, Any]], symbol_bbox: list[float]) -> dict[str, Any]:
    fills: Counter[str] = Counter()
    strokes: Counter[str] = Counter()
    widths: Counter[str] = Counter()
    candidates = 0
    search = expanded_bbox(symbol_bbox, 10.0, 8.0)
    for feature in raw_features:
        bbox = feature_bbox(feature)
        if not bbox or bbox_intersection_area(bbox, search) <= 0:
            continue
        props = feature.get("properties") or {}
        fill = props.get("source_style_hex")
        stroke = props.get("source_stroke_hex")
        if fill and fill not in {"#ffffff", "#fff", "#000000"}:
            fills[str(fill)] += 1
        if stroke and stroke != "#ffffff":
            strokes[str(stroke)] += 1
        if props.get("stroke_width") is not None:
            widths[str(props.get("stroke_width"))] += 1
        candidates += 1
    return {
        "symbol_fill_hex": fills.most_common(1)[0][0] if fills else None,
        "symbol_stroke_hex": strokes.most_common(1)[0][0] if strokes else None,
        "symbol_stroke_width": float(widths.most_common(1)[0][0]) if widths else None,
        "symbol_dash_pattern": "solid",
        "symbol_mean_color": fills.most_common(1)[0][0] if fills else None,
        "source_rect_index": None,
        "style_candidate_count": candidates,
    }


def build_legend_mapping_artifacts(
    *,
    run_id: str,
    collection_id: str,
    source_pdf: str | None,
    source_fingerprint: str,
    text_specs: list[dict[str, Any]],
    raw_features: list[dict[str, Any]],
    legend_bbox: list[float] | None,
    legend_crops: list[dict[str, Any]],
    page_number: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    primary_crop = next((crop for crop in legend_crops if crop.get("image_artifact_path_or_url")), None)
    transform = (primary_crop or {}).get("page_to_image_transform")
    if not transform and primary_crop:
        transform = page_to_image_transform(
            primary_crop.get("crop_bbox_page_pt"),
            primary_crop.get("image_width_px"),
            primary_crop.get("image_height_px"),
        )
    if not legend_bbox or not primary_crop:
        return [], [], [], [], {
            "legend_item_count": 0,
            "legend_symbol_count": 0,
            "legend_vector_def_count": 0,
            "missing_expected_symbol_count": 0,
            "ignored_extra_symbol_count": 0,
            "checkbox_to_vector_def_wiring_count": 0,
        }, []

    crop_id = str(primary_crop["legend_crop_id"])
    code_specs = [
        spec
        for spec in text_specs
        if spec.get("matched_code_candidate") in TARGET_LEGEND_CODES
        and bbox_contains_point(legend_bbox, bbox_center(spec.get("bbox_page_pt")))
    ]
    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for spec in code_specs:
        by_code[str(spec["matched_code_candidate"])].append(spec)

    rows: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    symbols: list[dict[str, Any]] = []
    vector_defs: list[dict[str, Any]] = []
    corrections: list[dict[str, Any]] = []
    missing_count = 0
    ignored_count = 0

    row_specs: list[tuple[str, list[dict[str, Any]], float]] = []
    for code in TARGET_LEGEND_CODES:
        specs = by_code.get(code, [])
        if not specs:
            continue
        specs = sorted(specs, key=lambda spec: ((spec.get("bbox_page_pt") or [0, 0, 0, 0])[1], (spec.get("bbox_page_pt") or [0, 0, 0, 0])[0]))
        row_y = median_float([(spec.get("bbox_page_pt") or [0, 0, 0, 0])[1] for spec in specs])
        row_specs.append((code, specs, row_y))
    row_specs.sort(key=lambda item: item[2])

    for index, (code, specs, row_y) in enumerate(row_specs, 1):
        next_y = row_specs[index][2] if index < len(row_specs) else row_y + 42.0
        row_top = max(legend_bbox[1], row_y - 15.0)
        row_bottom = min(legend_bbox[3], min(next_y - 6.0, row_y + 45.0))
        label_specs = [
            spec
            for spec in text_specs
            if (bbox := spec.get("bbox_page_pt"))
            and bbox_contains_point(legend_bbox, bbox_center(bbox))
            and bbox[0] >= legend_bbox[0] + 230.0
            and row_top <= bbox[1] <= row_bottom
        ]
        label_specs.sort(key=lambda spec: ((spec.get("bbox_page_pt") or [0, 0, 0, 0])[1], (spec.get("bbox_page_pt") or [0, 0, 0, 0])[0]))
        label_text_raw = " ".join(str(spec.get("raw_text") or "") for spec in label_specs).strip() or None
        label_fields = label_quality_fields(label_text_raw, code)
        line_count = len({round((spec.get("bbox_page_pt") or [0, 0, 0, 0])[1], 1) for spec in label_specs})
        symbol_group_bbox = [
            min((spec.get("bbox_page_pt") or [legend_bbox[0], 0, 0, 0])[0] for spec in specs) - 45.0,
            row_top,
            max((spec.get("bbox_page_pt") or [0, 0, legend_bbox[0], 0])[2] for spec in specs) + 45.0,
            row_bottom,
        ]
        label_bbox = None
        if label_specs:
            label_bbox = [
                min(float(spec["bbox_page_pt"][0]) for spec in label_specs),
                min(float(spec["bbox_page_pt"][1]) for spec in label_specs),
                max(float(spec["bbox_page_pt"][2]) for spec in label_specs),
                max(float(spec["bbox_page_pt"][3]) for spec in label_specs),
            ]
        row_bbox = [
            round(max(legend_bbox[0], min(symbol_group_bbox[0], (label_bbox or symbol_group_bbox)[0]) - 5.0), 3),
            round(row_top, 3),
            round(min(legend_bbox[2], max(symbol_group_bbox[2], (label_bbox or symbol_group_bbox)[2]) + 8.0), 3),
            round(row_bottom, 3),
        ]
        legend_row_id = f"legend-row-target-{index:04d}"
        legend_item_id = f"legend-item-{stable_hash(crop_id + code + str(round(row_y, 2)), 10)}"

        detected_symbols: list[dict[str, Any]] = []
        seen_roles: set[str] = set()
        for spec in sorted(specs, key=lambda spec: (spec.get("bbox_page_pt") or [0, 0, 0, 0])[0]):
            anchor_bbox = [float(value) for value in spec.get("bbox_page_pt")]
            role, order = symbol_role_for_code_anchor(anchor_bbox, legend_bbox)
            if role in seen_roles and role != "ignored_extra":
                continue
            seen_roles.add(role)
            symbol_bbox = estimate_symbol_bbox(anchor_bbox, role, legend_bbox)
            style = dominant_symbol_style(raw_features, symbol_bbox)
            symbol_id = f"legend-symbol-{len(symbols) + len(detected_symbols) + 1:04d}"
            status = "ignored_extra" if role == "ignored_extra" else "detected"
            if role == "ignored_extra":
                ignored_count += 1
            symbol = {
                "legend_symbol_id": symbol_id,
                "run_id": run_id,
                "collection_id": collection_id,
                "source_pdf": source_pdf,
                "source_fingerprint": source_fingerprint,
                "legend_crop_id": crop_id,
                "legend_row_id": legend_row_id,
                "legend_item_id": legend_item_id,
                "legend_column_index": 0,
                "symbol_order": order,
                "symbol_bbox_page_pt": symbol_bbox,
                "symbol_bbox_image_px": bbox_to_image_bbox(symbol_bbox, transform),
                **style,
                "symbol_source_rect_index": style.get("source_rect_index"),
                "symbol_role": role,
                "symbol_role_confidence": 0.86 if role in {"stav_stabil", "navrh"} else 0.62,
                "symbol_status": status,
                "review_status": "unreviewed" if role in {"stav_stabil", "navrh"} else "requires_review",
            }
            detected_symbols.append(symbol)

        normal_symbols = [symbol for symbol in detected_symbols if symbol["symbol_role"] in {"stav_stabil", "navrh"}]
        normal_roles = {symbol["symbol_role"] for symbol in normal_symbols}
        missing_roles = [role for role in ["stav_stabil", "navrh"] if role not in normal_roles]
        for role in missing_roles:
            missing_count += 1
            symbol_id = f"legend-symbol-{len(symbols) + len(detected_symbols) + 1:04d}"
            missing = {
                "legend_symbol_id": symbol_id,
                "run_id": run_id,
                "collection_id": collection_id,
                "source_pdf": source_pdf,
                "source_fingerprint": source_fingerprint,
                "legend_crop_id": crop_id,
                "legend_row_id": legend_row_id,
                "legend_item_id": legend_item_id,
                "legend_column_index": 0,
                "symbol_order": 1 if role == "stav_stabil" else 2,
                "symbol_bbox_page_pt": None,
                "symbol_bbox_image_px": None,
                "symbol_fill_hex": None,
                "symbol_stroke_hex": None,
                "symbol_stroke_width": None,
                "symbol_dash_pattern": None,
                "symbol_hatch_pattern": None,
                "symbol_mean_color": None,
                "symbol_source_rect_index": None,
                "symbol_role": role,
                "symbol_role_confidence": 0.0,
                "symbol_status": "missing_expected_symbol_requires_review",
                "review_status": "requires_review",
            }
            detected_symbols.append(missing)
            corrections.append(
                {
                    "correction_task_id": f"missing-symbol-{legend_row_id}-{role}",
                    "affected_id": legend_item_id,
                    "action": "missing_expected_symbol_requires_review",
                    "reason": f"{code} legend item did not expose expected {role} symbol; no style was fabricated",
                    "before_summary": "expected two normal legend symbols",
                    "after_summary": f"{role} marked requires_review without fill/stroke",
                    "operator_or_source": "deterministic_legend_row_extraction",
                    "timestamp": now_iso(),
                }
            )

        matched_vector_def_ids: list[str] = []
        for symbol in normal_symbols:
            class_type = "STAV" if symbol["symbol_role"] == "stav_stabil" else "NAVRH"
            class_type_id = 1 if class_type == "STAV" else 2
            vector_def_id = f"legend-vector-def-{len(vector_defs) + 1:04d}"
            matched_vector_def_ids.append(vector_def_id)
            vector_defs.append(
                {
                    "vector_def_id": vector_def_id,
                    "candidate_id": vector_def_id,
                    "run_id": run_id,
                    "collection_id": collection_id,
                    "source_pdf": source_pdf,
                    "source_fingerprint": source_fingerprint,
                    "page_number": page_number,
                    "definition_source": "legend_autocrop",
                    "legend_item_id": legend_item_id,
                    "legend_row_id": legend_row_id,
                    "legend_crop_id": crop_id,
                    "legend_column_index": 0,
                    "legend_symbol_id": symbol["legend_symbol_id"],
                    "symbol_order": symbol["symbol_order"],
                    "symbol_role": symbol["symbol_role"],
                    "symbol_bbox_page_pt": symbol["symbol_bbox_page_pt"],
                    "symbol_bbox_image_px": symbol["symbol_bbox_image_px"],
                    "source_rect_index": symbol.get("symbol_source_rect_index"),
                    "code_text": code,
                    "candidate_layer": "RZVP",
                    "candidate_class": code,
                    "candidate_type": class_type,
                    "up_class": code,
                    "class_type": class_type,
                    "class_type_id": class_type_id,
                    "fill_color_hex": symbol.get("symbol_fill_hex"),
                    "fill_hex": symbol.get("symbol_fill_hex"),
                    "stroke_color_hex": symbol.get("symbol_stroke_hex"),
                    "stroke_hex": symbol.get("symbol_stroke_hex"),
                    "stroke_width": symbol.get("symbol_stroke_width"),
                    "dash_pattern_normalized": symbol.get("symbol_dash_pattern") or "solid",
                    "has_dash_pattern": bool(symbol.get("symbol_dash_pattern") and symbol.get("symbol_dash_pattern") != "solid"),
                    "is_checked_for_mapping": False,
                    "review_status": "unreviewed",
                    "export_eligible": False,
                    "matched_feature_count": 0,
                    "requires_review": True,
                    "confidence": 0.72 if symbol.get("symbol_fill_hex") else 0.45,
                    "candidate_status": "legend_candidate_unreviewed",
                    "classification_status": "requires_review",
                    "legend_label_text": label_text_raw,
                    "legend_label_text_display": label_fields["label_text_display"],
                    "legend_label_text_status": label_fields["label_text_status"],
                    "sample_count": 1,
                    "emitted_feature_count": 0,
                    "sample_feature_ids": [],
                    "path_item_type_counts": {},
                    "rejected_reason": None,
                }
            )

        row_review = "requires_review" if missing_roles else "unreviewed"
        row = {
            "legend_row_id": legend_row_id,
            "run_id": run_id,
            "collection_id": collection_id,
            "source_pdf": source_pdf,
            "source_fingerprint": source_fingerprint,
            "legend_crop_id": crop_id,
            "legend_item_id": legend_item_id,
            "legend_column_index": 0,
            "legend_row_index_in_column": index,
            "row_bbox_page_pt": row_bbox,
            "row_bbox_image_px": bbox_to_image_bbox(row_bbox, transform),
            "symbol_group_bbox_page_pt": [round(value, 3) for value in symbol_group_bbox],
            "label_bbox_page_pt": [round(value, 3) for value in label_bbox] if label_bbox else None,
            "code_text": code,
            "target_code": code,
            "target_group": TARGET_CODE_CLASSES.get(code),
            **label_fields,
            "label_text_normalized": normalized_text(label_text_raw),
            "label_wrap_line_count": line_count,
            "is_wrapped_label": line_count > 1,
            "symbols": detected_symbols,
            "expected_symbol_count": 2,
            "detected_symbol_count": len([symbol for symbol in detected_symbols if symbol.get("symbol_status") == "detected"]),
            "normal_vector_def_row_count": len(matched_vector_def_ids),
            "ignored_extra_symbol_count": len([symbol for symbol in detected_symbols if symbol.get("symbol_role") == "ignored_extra"]),
            "missing_expected_symbol_count": len(missing_roles),
            "matched_vector_def_ids": matched_vector_def_ids,
            "proposed_up_layer": "RZVP",
            "proposed_up_class": code,
            "proposed_up_type": None,
            "is_in_scope": code in TARGET_CODE_CLASSES,
            "confidence": 0.78 if not missing_roles else 0.52,
            "requires_review": True,
            "review_status": row_review,
            "evidence_reason": "legend row detected from target code anchors and symbol swatches; approval is still required",
            "is_checked_for_mapping": False,
            "focused_legend_item_id": None,
            "export_eligible": False,
        }
        item = {
            "legend_item_id": legend_item_id,
            "run_id": run_id,
            "collection_id": collection_id,
            "source_pdf": source_pdf,
            "source_fingerprint": source_fingerprint,
            "legend_crop_id": crop_id,
            "legend_row_id": legend_row_id,
            "legend_column_index": 0,
            "legend_row_index_in_column": index,
            "code_text": code,
            **label_fields,
            "row_bbox_page_pt": row_bbox,
            "row_bbox_image_px": bbox_to_image_bbox(row_bbox, transform),
            "symbol_split_status": "missing_expected_symbol_requires_review" if missing_roles else "two_symbols_detected",
            "focused_legend_item_id": None,
            "is_focused": False,
            "is_checked_for_mapping": False,
            "review_status": row_review,
            "export_eligible": False,
            "normal_vector_def_row_count": len(matched_vector_def_ids),
            "missing_expected_symbol_count": len(missing_roles),
            "ignored_extra_symbol_count": len([symbol for symbol in detected_symbols if symbol.get("symbol_role") == "ignored_extra"]),
            "matched_vector_def_ids": matched_vector_def_ids,
            "status_reason": "checkbox/focus/review/export are intentionally separate states",
        }
        rows.append(row)
        items.append(item)
        symbols.extend(detected_symbols)

    stats = {
        "legend_item_count": len(items),
        "legend_symbol_count": len(symbols),
        "legend_vector_def_count": len(vector_defs),
        "legend_overlay_transform_count": 1 if transform else 0,
        "legend_column_count": 1,
        "two_row_vector_def_split_count": len([item for item in items if item.get("normal_vector_def_row_count") == 2]),
        "missing_expected_symbol_count": missing_count,
        "ignored_extra_symbol_count": ignored_count,
        "checkbox_to_vector_def_wiring_count": len([item for item in items if item.get("matched_vector_def_ids")]),
        "focused_legend_item_count": 0,
        "checked_legend_item_count": 0,
        "exportable_target_count": 0,
    }
    return rows, items, symbols, vector_defs, stats, corrections


def build_agent_legend_proposals(
    *,
    run_id: str,
    collection_id: str,
    legend_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for index, row in enumerate(legend_rows, 1):
        code = row.get("code_text") or row.get("target_code")
        if code not in TARGET_CODE_CLASSES:
            continue
        proposals.append(
            {
                "agent_legend_proposal_id": f"agent-legend-proposal-{index:04d}",
                "run_id": run_id,
                "collection_id": collection_id,
                "legend_crop_id": row.get("legend_crop_id"),
                "legend_row_id": row.get("legend_row_id"),
                "code_text": code,
                "label_text": row.get("label_text_display") or row.get("label_text_raw") or row.get("anchor_text"),
                "label_text_raw": row.get("label_text_raw"),
                "label_text_status": row.get("label_text_status"),
                "label_text_source": row.get("label_text_source"),
                "proposed_up_layer": "RZVP",
                "proposed_up_class": code,
                "proposed_up_type": None,
                "confidence": 0.5,
                "reason": "fake provider mirrors deterministic target-code row; operator approval is required",
                "model_or_agent_source": "fake_legend_provider_v1",
                "raw_response_ref": None,
                "validation_status": "agent_proposed",
                "review_status": "requires_review",
                "export_eligible": False,
            }
        )
    return proposals


def enrich_geojson_collection(
    collection: dict[str, Any],
    *,
    source_filename: str | None,
    source_url: str | None,
    source_origin: str = "geojson",
) -> dict[str, Any]:
    source_fingerprint = collection_fingerprint(collection)
    run_id, collection_id = run_ids(source_fingerprint)
    features = collection.get("features") or []
    detection = detection_for_geojson(source_filename=source_filename, source_url=source_url, feature_count=len(features))
    vector_definitions: dict[tuple[Any, ...], dict[str, Any]] = {}
    text_definitions: dict[str, dict[str, Any]] = {}
    for feature in features:
        props = feature.setdefault("properties", {})
        style = props.get("style_hex") or props.get("source_style_hex")
        key = (style, props.get("source_stroke_hex"), props.get("LAYER"), props.get("CLASS"), props.get("TYPE"))
        if key not in vector_definitions:
            vector_def_id = f"vector-def-{len(vector_definitions) + 1:04d}"
            vector_definitions[key] = {
                "vector_def_id": vector_def_id,
                "candidate_id": vector_def_id,
                "run_id": run_id,
                "collection_id": collection_id,
                "source_pdf": collection.get("source_pdf"),
                "source_fingerprint": source_fingerprint,
                "page_number": props.get("page"),
                "drawing_index": props.get("source_drawing_index"),
                "drawing_group_id": stable_hash(repr(key), 12),
                "path_item_type_counts": props.get("source_path_item_type_counts") or {},
                "has_l": False,
                "has_c": False,
                "has_qu": False,
                "has_re": False,
                "has_close_path": True,
                "is_closed_candidate": props.get("IS_CLOSED") is True,
                "is_filled": bool(style),
                "is_stroked": bool(props.get("source_stroke_hex")),
                "fill_color_rgb": props.get("style_rgb"),
                "fill_color_hex": style,
                "fill_hex": style,
                "fill_opacity": props.get("fill_opacity"),
                "stroke_color_rgb": None,
                "stroke_color_hex": props.get("source_stroke_hex"),
                "stroke_hex": props.get("source_stroke_hex"),
                "stroke_opacity": props.get("source_stroke_opacity"),
                "stroke_width": props.get("stroke_width"),
                "dash_pattern_raw": props.get("dash_array"),
                "dash_array": props.get("dash_array"),
                "dash_phase": None,
                "dash_pattern_normalized": None,
                "has_dash_pattern": bool(props.get("dash_array")),
                "source_layer_name": props.get("source_layer_name"),
                "source_ocg_name": None,
                "even_odd_fill_rule": None,
                "bbox_page_pt": props.get("bbox_page_pt") or geometry_bbox(feature.get("geometry")),
                "area_page_pt2": 0.0,
                "ring_count": 0,
                "hole_count": 0,
                "component_count": 0,
                "source_path_command_count": 0,
                "flattened_curve_segment_count": 0,
                "simplification_tolerance": 0,
                "rejected_reason": None,
                "emitted_feature_count": 0,
                "sample_feature_ids": [],
                "classification_status": props.get("classification_status") or "fixture_or_geojson",
                "candidate_layer": props.get("LAYER"),
                "candidate_class": props.get("CLASS"),
                "candidate_type": props.get("TYPE"),
                "candidate_status": "candidate",
                "sample_count": 0,
            }
        group = vector_definitions[key]
        group["sample_count"] += 1
        group["emitted_feature_count"] += 1
        group["ring_count"] += 1
        group["hole_count"] += max(0, len((feature.get("geometry") or {}).get("coordinates") or []) - 1)
        group["component_count"] += 1
        group["area_page_pt2"] += geometry_area(feature.get("geometry") or {})
        group["sample_feature_ids"] = [*group["sample_feature_ids"], str(feature.get("id") or props.get("FID"))][:8]
        if props.get("text_id"):
            text_key = str(props.get("text_id"))
            text_definitions.setdefault(
                text_key,
                {
                    "text_def_id": f"text-def-{len(text_definitions) + 1:04d}",
                    "candidate_id": f"text-def-{len(text_definitions) + 1:04d}",
                    "run_id": run_id,
                    "collection_id": collection_id,
                    "source_pdf": collection.get("source_pdf"),
                    "source_fingerprint": source_fingerprint,
                    "page_number": props.get("page"),
                    "raw_text": text_key,
                    "normalized_text": normalized_text(text_key),
                    "matched_code_candidate": detect_target_code(text_key),
                    "matched_label_candidate": None,
                    "sample_text": text_key,
                    "sample_count": 0,
                    "text_role": "change_label" if props.get("LAYER") == "ZMEN" else "source_label",
                    "candidate_status": "candidate",
                },
            )
            text_definitions[text_key]["sample_count"] += 1

    vector_defs = list(vector_definitions.values())
    text_defs = list(text_definitions.values())
    classification_proposals = build_classification_proposals(
        vector_definitions=vector_defs,
        text_definitions=text_defs,
        run_id=run_id,
        collection_id=collection_id,
    )
    legend_crops = build_legend_crops(
        run_id=run_id,
        collection_id=collection_id,
        source_pdf=collection.get("source_pdf"),
        source_fingerprint=source_fingerprint,
        text_definitions=text_defs,
        classification_proposals=classification_proposals,
    )
    legend_rows = build_legend_rows(
        run_id=run_id,
        collection_id=collection_id,
        source_pdf=collection.get("source_pdf"),
        source_fingerprint=source_fingerprint,
        text_specs=text_defs,
        legend_bbox=None,
        legend_crops=legend_crops,
    )
    pipeline_traces = [
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=1, step_name="source_input", algorithm=source_origin, input_count=1, output_count=1),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=2, step_name="source_detection", algorithm=detection["detection_algorithm"], input_count=1, output_count=1),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=3, step_name="vector_definition_grouping", algorithm="geojson_property_grouping_v1", input_count=len(features), output_count=len(vector_defs)),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=4, step_name="semantic_classification", algorithm="target_scope_evidence_v1", input_count=len(vector_defs), output_count=len(classification_proposals)),
    ]
    collection.update(
        {
            "run_id": run_id,
            "collection_id": collection_id,
            "source_filename": source_filename,
            "source_type": "geojson",
            "source_origin": source_origin,
            "source_fingerprint": source_fingerprint,
            "plan_snapshot_available": False,
            "plan_snapshot_source": "embedded_raster" if source_filename and "kvetnice" in source_filename.lower() else "unavailable",
            "sample_legend_crop_available": False,
            "legend_crop_source": "unavailable_geojson_only_sample",
            "legend_unavailable_reason": "Květnice bundled sample is GeoJSON-only and has no source PDF crop artifact.",
            "feature_count": len(features),
            "vector_def_count": len(vector_defs),
            "text_def_count": len(text_defs),
            "legend_crop_count": len(legend_crops),
            "legend_row_count": len(legend_rows),
            "error_count": 0,
            "classification_status": collection.get("classification_status") or "requires_review",
            "source_detection": detection,
            "vector_definitions": vector_defs,
            "text_definitions": text_defs,
            "text_specs": text_defs,
            "classification_proposals": classification_proposals,
            "classification_traces": classification_proposals,
            "legend_crops": legend_crops,
            "legend_candidates": [],
            "legend_rows": legend_rows,
            "pipeline_traces": pipeline_traces,
            "vector_extraction_traces": [],
            "text_extraction_traces": [],
            "geometry_error_candidates": [],
            "structured_errors": [],
            "primary_extraction_mode": "geojson_features",
            "raw_features_are_debug_only": False,
        }
    )
    return collection


def finalize_pdf_collection(
    collection: dict[str, Any],
    *,
    pdf_path: Path,
    source_url: str | None,
    page: Any,
    drawings: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    page_number: int,
    selected_algorithm: str,
) -> dict[str, Any]:
    source_fingerprint = file_fingerprint(pdf_path)
    run_id, collection_id = run_ids(source_fingerprint)
    features = collection.get("features") or []
    raw_features = features
    page_width, page_height = page_dimensions(collection, page)
    text_count = text_span_count(page)
    plan_snapshot = render_plan_page_snapshot(page=page, collection_id=collection_id, page_number=page_number)
    detection = detect_source(
        source_filename=pdf_path.name,
        source_url=source_url,
        page_count=diagnostics.get("page_count", 1),
        drawing_count=len(drawings),
        image_count=diagnostics.get("image_count", 0),
        text_count=text_count,
    )
    text_specs, text_definitions = extract_text_specs(
        page=page,
        run_id=run_id,
        collection_id=collection_id,
        source_pdf=pdf_path.name,
        source_fingerprint=source_fingerprint,
        page_number=page_number,
    )
    legend_detection = derive_legend_bbox(text_specs=text_specs, page_width=page_width, page_height=page_height)
    legend_bbox = legend_detection.get("bbox")
    feature_region_stats = classify_source_regions(
        raw_features,
        page_width=page_width,
        page_height=page_height,
        legend_bbox=legend_bbox,
    )
    tessellation = analyze_tessellation_fragments(raw_features, page_width=page_width, page_height=page_height)
    fragment_role_stats = classify_fragment_roles(
        raw_features,
        page_width=page_width,
        page_height=page_height,
        tessellation=tessellation,
    )
    vector_specs, vector_definitions, vector_traces, geometry_errors = build_vector_records(
        drawings=drawings,
        features=raw_features,
        run_id=run_id,
        collection_id=collection_id,
        source_pdf=pdf_path.name,
        source_fingerprint=source_fingerprint,
        page_number=page_number,
        algorithm=selected_algorithm,
    )
    classification_proposals = build_classification_proposals(
        vector_definitions=vector_definitions,
        text_definitions=text_definitions,
        run_id=run_id,
        collection_id=collection_id,
    )
    legend_crops = build_legend_crops(
        run_id=run_id,
        collection_id=collection_id,
        source_pdf=pdf_path.name,
        source_fingerprint=source_fingerprint,
        text_definitions=text_definitions,
        classification_proposals=classification_proposals,
        page=page,
        legend_bbox=legend_bbox,
        legend_detection=legend_detection,
        feature_region_stats=feature_region_stats,
    )
    fallback_legend_rows = build_legend_rows(
        run_id=run_id,
        collection_id=collection_id,
        source_pdf=pdf_path.name,
        source_fingerprint=source_fingerprint,
        text_specs=text_specs,
        legend_bbox=legend_bbox,
        legend_crops=legend_crops,
    )
    (
        rich_legend_rows,
        legend_items,
        legend_symbols,
        legend_vector_definitions,
        legend_mapping_stats,
        legend_corrections,
    ) = build_legend_mapping_artifacts(
        run_id=run_id,
        collection_id=collection_id,
        source_pdf=pdf_path.name,
        source_fingerprint=source_fingerprint,
        text_specs=text_specs,
        raw_features=raw_features,
        legend_bbox=legend_bbox,
        legend_crops=legend_crops,
        page_number=page_number,
    )
    legend_rows = rich_legend_rows or fallback_legend_rows
    vector_definitions = [*vector_definitions, *legend_vector_definitions]
    vector_specs = [*vector_specs, *legend_vector_definitions]
    agent_legend_proposals = build_agent_legend_proposals(
        run_id=run_id,
        collection_id=collection_id,
        legend_rows=legend_rows,
    )
    classification_proposals = build_classification_proposals(
        vector_definitions=vector_definitions,
        text_definitions=text_definitions,
        run_id=run_id,
        collection_id=collection_id,
    )
    primary_features, merge_stats, merge_errors = merge_tessellated_fill_features(
        raw_features,
        run_id=run_id,
        collection_id=collection_id,
        source_url=source_url,
        source_pdf=pdf_path.name,
        source_fingerprint=source_fingerprint,
        page_number=page_number,
        tessellation=tessellation,
    )
    spatial_association_stats = associate_features_with_target_text(primary_features, text_specs)
    feature_proposal_stats = annotate_primary_features(
        primary_features,
        legend_items=legend_items,
        legend_vector_definitions=legend_vector_definitions,
    )
    artifact_diagnostics = build_visual_artifact_diagnostics(raw_features, primary_features)
    up_extraction_profile = build_up_extraction_profile(
        pdf_name=pdf_path.name,
        raw_features=raw_features,
        primary_features=primary_features,
        text_specs=text_specs,
        legend_detection=legend_detection,
        artifact_diagnostics=artifact_diagnostics,
    )
    attach_method_profile_to_features(primary_features, up_extraction_profile)
    structured_errors: list[dict[str, Any]] = []
    if selected_algorithm != "vector_fill_style_polygon_v1":
        structured_errors.append(
            structured_error(
                run_id=run_id,
                collection_id=collection_id,
                source_url=source_url,
                source_filename=pdf_path.name,
                source_fingerprint=source_fingerprint,
                step="vector_extraction",
                algorithm=selected_algorithm,
                severity="warning",
                error_code="algorithm_routed_pending_or_diagnostic",
                message=f"selected algorithm {selected_algorithm} did not emit trusted vector polygons",
                recovery_action="review diagnostics or implement routed algorithm profile",
                retryable=False,
            )
        )
    for merge_error in merge_errors:
        structured_errors.append(
            structured_error(
                run_id=run_id,
                collection_id=collection_id,
                source_url=source_url,
                source_filename=pdf_path.name,
                source_fingerprint=source_fingerprint,
                step="tessellated_fill_merge",
                algorithm="vector_tessellated_fill_merge_v1",
                severity="warning",
                error_code=str(merge_error.get("error_code") or "tessellated_merge_warning"),
                message=str(merge_error.get("message") or merge_error),
                recovery_action="inspect raw_fragment_debug_sample and rerun with manual crop/style constraints",
                retryable=True,
            )
        )
    pipeline_traces = [
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=1, step_name="source_input", algorithm="pdf_upload_or_url_v1", input_count=1, output_count=1),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=2, step_name="source_detection", algorithm=detection["detection_algorithm"], input_count=1, output_count=1, warning_count=len(detection.get("warnings") or [])),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=3, step_name="pdf_metadata", algorithm="pymupdf_metadata_v1", input_count=1, output_count=diagnostics.get("page_count", 1)),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=4, step_name="plan_page_snapshot", algorithm="pymupdf_page_render_snapshot_v1", input_count=1, output_count=1 if plan_snapshot.get("plan_snapshot_available") else 0, status="ok" if plan_snapshot.get("plan_snapshot_available") else "warning", details=plan_snapshot),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=5, step_name="vector_drawings_inventory", algorithm="page_get_drawings_v1", input_count=diagnostics.get("page_count", 1), output_count=len(drawings)),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=6, step_name="text_inventory", algorithm="page_get_text_dict_v1", input_count=1, output_count=len(text_specs)),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=7, step_name="vector_path_polygonization", algorithm=selected_algorithm, input_count=len(drawings), output_count=len(raw_features), rejected_count=len(geometry_errors)),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=8, step_name="dash_pattern_extraction", algorithm="pymupdf_dashes_parse_v2", input_count=len(drawings), output_count=len([row for row in vector_specs if row.get("has_dash_pattern")])),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=9, step_name="text_spec_extraction", algorithm="text_span_spec_v1", input_count=text_count, output_count=len(text_specs)),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=10, step_name="map_legend_region_separation", algorithm="right_panel_text_density_region_v1", input_count=len(raw_features), output_count=feature_region_stats.get("map_body_feature_count", 0), details=feature_region_stats),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=11, step_name="tessellation_detection", algorithm="stripe_fragment_detector_v1", input_count=len(raw_features), output_count=1 if tessellation.get("tessellated_fill_detected") else 0, status="warning" if tessellation.get("tessellated_fill_detected") else "ok", details=tessellation),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=12, step_name="fragment_role_classification", algorithm="fragment_role_classification_v1", input_count=len(raw_features), output_count=fragment_role_stats.get("trusted_merge_input_count", 0), details=fragment_role_stats),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=13, step_name="tessellated_fill_merge", algorithm="vector_tessellated_fill_merge_v1", input_count=len(raw_features), output_count=len(primary_features), warning_count=len(merge_errors), runtime_ms=merge_stats.get("merge_runtime_ms", 0), status="ok" if not merge_errors else "warning", details={key: value for key, value in merge_stats.items() if key != "merged_groups"}),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=14, step_name="visual_quality_gate", algorithm="raw_fragment_false_success_gate_v1+visual_artifact_diagnostics_v1", input_count=len(raw_features), output_count=len(primary_features), warning_count=artifact_diagnostics.get("artifact_requires_review_feature_count", 0), status="ok" if len(primary_features) < len(raw_features) or not tessellation.get("tessellated_fill_detected") else "warning", details={"raw_fragment_count": len(raw_features), "primary_feature_count": len(primary_features), "primary_extraction_mode": merge_stats.get("primary_extraction_mode", tessellation.get("primary_extraction_mode")), "artifact_diagnostics": artifact_diagnostics}),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=15, step_name="legend_autocrop", algorithm="legend_candidate_evidence_ranker_v8_1+autocrop_render_v1", input_count=len(text_specs), output_count=len([row for row in legend_crops if row.get("image_artifact_path_or_url")]), warning_count=len([row for row in legend_crops if row.get("review_status") == "unavailable"]), details=legend_detection),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=16, step_name="legend_row_extraction", algorithm="target_code_row_symbol_split_v1+label_quality_v1", input_count=len(text_specs), output_count=len(legend_rows), warning_count=len([row for row in legend_rows if row.get("review_status") == "requires_review"]), details=legend_mapping_stats),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=17, step_name="legend_item_to_vector_def_split", algorithm="legend_item_two_symbol_vector_def_split_v1", input_count=len(legend_items), output_count=len(legend_vector_definitions), warning_count=legend_mapping_stats.get("missing_expected_symbol_count", 0), details=legend_mapping_stats),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=18, step_name="vector_definition_grouping", algorithm="style_path_grouping_v1+legend_vector_def_bridge_v1", input_count=len(drawings), output_count=len(vector_definitions)),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=19, step_name="text_definition_grouping", algorithm="normalized_text_grouping_v1", input_count=len(text_specs), output_count=len(text_definitions)),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=20, step_name="semantic_classification", algorithm="target_scope_evidence_v1", input_count=len(vector_definitions), output_count=len(classification_proposals)),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=21, step_name="spatial_association", algorithm=spatial_association_stats["association_algorithm"], input_count=len(primary_features), output_count=spatial_association_stats["feature_text_association_count"], details=spatial_association_stats),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=22, step_name="feature_proposal_annotation", algorithm=feature_proposal_stats["algorithm"], input_count=len(primary_features), output_count=feature_proposal_stats["feature_proposal_count"], warning_count=feature_proposal_stats["artifact_requires_review_feature_count"], details=feature_proposal_stats),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=23, step_name="method_aware_extraction_profile", algorithm=up_extraction_profile["algorithm"], input_count=len(raw_features), output_count=len(up_extraction_profile.get("method_rows") or []), warning_count=up_extraction_profile.get("manual_split_required_count", 0), status="requires_review" if up_extraction_profile.get("manual_split_required_count") else "ok", details=up_extraction_profile),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=24, step_name="target_scope_filtering", algorithm="bydleni_rekreace_smisene_scope_v1", input_count=len(classification_proposals), output_count=len([row for row in classification_proposals if row.get("is_inscope_bydleni_related")])),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=25, step_name="manual_legend_crop_fallback", algorithm="operator_bbox_fallback_v1", input_count=1, output_count=1, status="requires_review"),
        pipeline_step(run_id=run_id, collection_id=collection_id, step_order=26, step_name="export_candidate_generation", algorithm="jsonl_csv_export_bridge_v1", input_count=1, output_count=14),
    ]
    collection.update(
        {
            "run_id": run_id,
            "collection_id": collection_id,
            "source_filename": pdf_path.name,
            "source_type": detection["source_type"],
            "source_fingerprint": source_fingerprint,
            "plan_snapshot_available": plan_snapshot.get("plan_snapshot_available"),
            "plan_snapshot_artifact_path": plan_snapshot.get("plan_snapshot_artifact_path"),
            "plan_snapshot_url": plan_snapshot.get("plan_snapshot_url"),
            "plan_snapshot_source": plan_snapshot.get("plan_snapshot_source"),
            "plan_snapshot_scale": plan_snapshot.get("plan_snapshot_scale"),
            "plan_snapshot_page_number": plan_snapshot.get("plan_snapshot_page_number"),
            "plan_snapshot_transform": plan_snapshot.get("plan_snapshot_transform"),
            "plan_snapshot_width_px": plan_snapshot.get("plan_snapshot_width_px"),
            "plan_snapshot_height_px": plan_snapshot.get("plan_snapshot_height_px"),
            "feature_count": len(primary_features),
            "raw_fragment_count": len(raw_features),
            "primary_extraction_mode": merge_stats.get("primary_extraction_mode", tessellation.get("primary_extraction_mode")),
            "raw_features_are_debug_only": merge_stats.get("raw_features_are_debug_only", False),
            "vector_def_count": len(vector_definitions),
            "text_def_count": len(text_definitions),
            "legend_crop_count": len(legend_crops),
            "legend_row_count": len(legend_rows),
            "legend_item_count": len(legend_items),
            "legend_symbol_count": len(legend_symbols),
            "error_count": len(structured_errors) + len(geometry_errors),
            "features": primary_features,
            "source_detection": detection,
            "vector_specs": vector_specs,
            "vector_definitions": vector_definitions,
            "text_specs": text_specs[:2000],
            "text_spec_count_total": len(text_specs),
            "text_definitions": text_definitions,
            "classification_proposals": classification_proposals,
            "classification_traces": classification_proposals,
            "legend_crops": legend_crops,
            "legend_crop_source": "auto" if any(row.get("image_artifact_path_or_url") for row in legend_crops) else "unavailable",
            "legend_candidates": legend_detection.get("legend_candidates", []),
            "legend_rows": legend_rows,
            "legend_items": legend_items,
            "legend_symbols": legend_symbols,
            "legend_mapping_stats": legend_mapping_stats,
            "agent_legend_proposals": agent_legend_proposals,
            "legend_detection": legend_detection,
            "manual_legend_crop_fallbacks": [
                {
                    "manual_crop_id": "manual-legend-suggested-0001",
                    "run_id": run_id,
                    "collection_id": collection_id,
                    "source_pdf": pdf_path.name,
                    "source_fingerprint": source_fingerprint,
                    "suggested_bbox_page_pt": legend_bbox,
                    "status": "available_for_operator",
                    "reason": "autocrop is heuristic; operator can redraw this bbox when legend rows or symbol colors need correction",
                }
            ],
            "tessellation_metrics": tessellation,
            "fragment_role_stats": fragment_role_stats,
            "merge_stats": merge_stats,
            "artifact_diagnostics": artifact_diagnostics,
            "up_extraction_profile": up_extraction_profile,
            "feature_region_stats": feature_region_stats,
            "spatial_association_stats": spatial_association_stats,
            "feature_proposal_stats": feature_proposal_stats,
            "task_stats": {
                "raw_fragments": len(raw_features),
                "primary_features": len(primary_features),
                "raw_to_primary_ratio": round(len(raw_features) / max(len(primary_features), 1), 3),
                "vector_definitions": len(vector_definitions),
                "text_definitions": len(text_definitions),
                "legend_crops": len(legend_crops),
                "legend_rows": len(legend_rows),
                "legend_items": len(legend_items),
                "legend_symbols": len(legend_symbols),
                "legend_vector_definitions": len(legend_vector_definitions),
                "two_row_vector_def_split_count": legend_mapping_stats.get("two_row_vector_def_split_count", 0),
                "missing_expected_symbol_count": legend_mapping_stats.get("missing_expected_symbol_count", 0),
                "ignored_extra_symbol_count": legend_mapping_stats.get("ignored_extra_symbol_count", 0),
                "checkbox_to_vector_def_wiring_count": legend_mapping_stats.get("checkbox_to_vector_def_wiring_count", 0),
                "plan_snapshot_available": bool(plan_snapshot.get("plan_snapshot_available")),
                "white_fill_fragment_count": artifact_diagnostics.get("white_fill_fragment_count", 0),
                "white_fill_fragment_area": artifact_diagnostics.get("white_fill_fragment_area", 0),
                "background_mask_candidate_count": artifact_diagnostics.get("background_mask_candidate_count", 0),
                "rectangular_hole_count": artifact_diagnostics.get("rectangular_hole_count", 0),
                "rectangular_hole_area_ratio": artifact_diagnostics.get("rectangular_hole_area_ratio", 0),
                "holes_removed_as_artifacts_count": artifact_diagnostics.get("holes_removed_as_artifacts_count", 0),
                "holes_kept_count": artifact_diagnostics.get("holes_kept_count", 0),
                "hole_review_required_count": artifact_diagnostics.get("hole_review_required_count", 0),
                "triangular_void_count": artifact_diagnostics.get("triangular_void_count", 0),
                "small_void_count": artifact_diagnostics.get("small_void_count", 0),
                "void_area_ratio": artifact_diagnostics.get("void_area_ratio", 0),
                "void_removed_as_artifact_count": artifact_diagnostics.get("void_removed_as_artifact_count", 0),
                "void_kept_count": artifact_diagnostics.get("void_kept_count", 0),
                "void_requires_review_count": artifact_diagnostics.get("void_requires_review_count", 0),
                "max_spike_score": artifact_diagnostics.get("max_spike_score", 0),
                "spike_count": artifact_diagnostics.get("spike_count", 0),
                "spike_fixed_count": artifact_diagnostics.get("spike_fixed_count", 0),
                "spike_review_required_count": artifact_diagnostics.get("spike_review_required_count", 0),
                "needle_count": artifact_diagnostics.get("needle_count", 0),
                "sliver_component_count": artifact_diagnostics.get("sliver_component_count", 0),
                "thin_corridor_count": artifact_diagnostics.get("thin_corridor_count", 0),
                "sliver_removed_count": artifact_diagnostics.get("sliver_removed_count", 0),
                "thin_corridor_removed_count": artifact_diagnostics.get("thin_corridor_removed_count", 0),
                "artifact_requires_review_feature_count": artifact_diagnostics.get("artifact_requires_review_feature_count", 0),
                "hole_cleanup_removed_hole_count": artifact_diagnostics.get("hole_cleanup_removed_hole_count", 0),
                "hole_cleanup_review_required_hole_count": artifact_diagnostics.get("hole_cleanup_review_required_hole_count", 0),
                "manual_split_required_count": up_extraction_profile.get("manual_split_required_count", 0),
                "hatch_candidate_count": up_extraction_profile.get("hatch_candidate_count", 0),
                "dotted_boundary_candidate_count": up_extraction_profile.get("dotted_boundary_candidate_count", 0),
                "export_blocked_feature_count": artifact_diagnostics.get("export_blocked_feature_count", 0),
                "structured_errors": len(structured_errors),
                "geometry_errors": len(geometry_errors),
                "requires_review_rows": len([row for row in legend_rows if row.get("review_status") == "requires_review"]),
                "exportable_after_review_count": legend_mapping_stats.get("exportable_target_count", 0),
            },
            "correction_tasks": [
                {
                    "correction_task_id": "kamenice-hlv-raw-fragment-primary-result",
                    "status": "fixed" if tessellation.get("tessellated_fill_detected") and merge_stats.get("raw_features_are_debug_only") else "not_applicable",
                    "algorithm": "vector_tessellated_fill_merge_v1",
                    "result": "primary features use merged map-body polygons; raw tessellation fragments are retained only as debug samples",
                },
                {
                    "correction_task_id": "legend-autocrop-and-row-review",
                    "status": "requires_review",
                    "algorithm": "right_panel_autocrop_render_v1",
                    "result": "autocrop artifact and target-code legend rows are exposed for operator confirmation",
                },
                {
                    "correction_task_id": "visual-artifact-review",
                    "status": "requires_review" if artifact_diagnostics.get("artifact_requires_review_feature_count") else "not_applicable",
                    "algorithm": "visual_artifact_diagnostics_v1+geometry_artifact_review_flagging_v1",
                    "result": "white/background, void, rectangular hole, spike, needle, sliver, and thin-corridor metrics are recorded; uncertain geometry is review-only rather than silently mutated",
                },
                {
                    "correction_task_id": "semantic-hatch-boundary-split",
                    "status": "manual_required" if up_extraction_profile.get("manual_split_required_count") else "not_applicable",
                    "algorithm": up_extraction_profile["algorithm"],
                    "result": "fill-only polygons remain review-blocked where hatch, dotted-boundary, or thick-boundary evidence indicates semantic split risk",
                },
                *legend_corrections,
            ],
            "pipeline_traces": pipeline_traces,
            "vector_extraction_traces": vector_traces[:2000],
            "vector_extraction_trace_count_total": len(vector_traces),
            "text_extraction_traces": text_specs[:2000],
            "text_extraction_trace_count_total": len(text_specs),
            "geometry_error_candidates": geometry_errors[:500],
            "geometry_error_count_total": len(geometry_errors),
            "structured_errors": structured_errors,
            "raw_fragment_debug_sample": raw_features[:500] if merge_stats.get("raw_features_are_debug_only") else [],
            "diagnostics": {
                **(collection.get("diagnostics") or diagnostics),
                "source_detection": detection,
                "error_count": len(structured_errors) + len(geometry_errors),
                "vector_def_count": len(vector_definitions),
                "text_def_count": len(text_definitions),
                "legend_crop_count": len(legend_crops),
                "legend_row_count": len(legend_rows),
                "legend_item_count": len(legend_items),
                "legend_symbol_count": len(legend_symbols),
                "raw_fragment_count": len(raw_features),
                "primary_feature_count": len(primary_features),
                "primary_extraction_mode": merge_stats.get("primary_extraction_mode", tessellation.get("primary_extraction_mode")),
                "raw_features_are_debug_only": merge_stats.get("raw_features_are_debug_only", False),
                "plan_snapshot": plan_snapshot,
                "tessellation_metrics": tessellation,
                "fragment_role_stats": fragment_role_stats,
                "merge_stats": merge_stats,
                "artifact_diagnostics": artifact_diagnostics,
                "feature_region_stats": feature_region_stats,
                "legend_detection": legend_detection,
                "up_extraction_profile": up_extraction_profile,
                "legend_mapping_stats": legend_mapping_stats,
                "spatial_association_stats": spatial_association_stats,
                "feature_proposal_stats": feature_proposal_stats,
            },
        }
    )
    return collection


EXPORT_ROWS = {
    "pipeline_traces": ("pipeline_traces", "jsonl"),
    "vector_traces": ("vector_extraction_traces", "jsonl"),
    "text_traces": ("text_extraction_traces", "jsonl"),
    "vector_definitions": ("vector_definitions", "csv"),
    "text_definitions": ("text_definitions", "csv"),
    "legend_crops": ("legend_crops", "csv"),
    "legend_items": ("legend_items", "csv"),
    "legend_symbols": ("legend_symbols", "csv"),
    "classification_proposals": ("classification_proposals", "csv"),
    "structured_errors": ("structured_errors", "csv"),
    "legend_rows": ("legend_rows", "csv"),
    "task_stats": ("task_stats", "csv"),
    "correction_tasks": ("correction_tasks", "csv"),
    "agent_legend_proposals": ("agent_legend_proposals", "csv"),
    "raw_fragment_debug_sample": ("raw_fragment_debug_sample", "jsonl"),
}


def flatten_for_csv(row: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (dict, list, tuple)):
            flattened[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            flattened[key] = value
    return flattened


def export_collection(collection: dict[str, Any], kind: str) -> tuple[str, str, str]:
    if kind not in EXPORT_ROWS:
        raise KeyError(kind)
    key, fmt = EXPORT_ROWS[kind]
    rows = collection.get(key) or []
    if isinstance(rows, dict):
        rows = [rows]
    run_id = collection.get("run_id")
    collection_id = collection.get("collection_id")
    source_filename = collection.get("source_filename")
    source_fingerprint = collection.get("source_fingerprint")
    enriched_rows = [
        {
            "run_id": row.get("run_id") or run_id,
            "collection_id": row.get("collection_id") or collection_id,
            "source_filename": row.get("source_filename") or source_filename,
            "source_fingerprint": row.get("source_fingerprint") or source_fingerprint,
            **row,
        }
        for row in rows
    ]
    filename = f"{collection_id or 'collection'}_{kind}.{fmt}"
    if fmt == "jsonl":
        return "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in enriched_rows), "application/x-ndjson", filename
    output = io.StringIO()
    flattened = [flatten_for_csv(row) for row in enriched_rows]
    headers = sorted({key for row in flattened for key in row})
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    writer.writerows(flattened)
    return output.getvalue(), "text/csv", filename
