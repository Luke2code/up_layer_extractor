from __future__ import annotations

from dataclasses import dataclass
from typing import Any


Coordinate = list[float]
Ring = list[Coordinate]


@dataclass(frozen=True)
class GeometryValidation:
    geometry_type: str
    is_single_polygon: bool
    is_closed_after: bool
    is_valid_after: bool
    area_before: float
    area_after: float
    area_delta_pct: float
    review_note_required: bool
    errors: list[str]


def close_ring(ring: Ring) -> Ring:
    if not ring:
        return ring
    first = ring[0]
    last = ring[-1]
    if len(first) < 2 or len(last) < 2:
        return ring
    if abs(first[0] - last[0]) > 1e-6 or abs(first[1] - last[1]) > 1e-6:
        return [*ring, [first[0], first[1]]]
    return ring


def is_closed_ring(ring: Ring) -> bool:
    if len(ring) < 4:
        return False
    first = ring[0]
    last = ring[-1]
    return abs(first[0] - last[0]) <= 1e-6 and abs(first[1] - last[1]) <= 1e-6


def ring_area(ring: Ring) -> float:
    closed = close_ring(ring)
    if len(closed) < 4:
        return 0.0
    total = 0.0
    for left, right in zip(closed, closed[1:]):
        total += left[0] * right[1] - right[0] * left[1]
    return total / 2.0


def polygon_area(coordinates: list[Ring]) -> float:
    if not coordinates:
        return 0.0
    outer = abs(ring_area(coordinates[0]))
    holes = sum(abs(ring_area(ring)) for ring in coordinates[1:])
    return max(0.0, outer - holes)


def geometry_area(geometry: dict[str, Any] | None) -> float:
    if not geometry:
        return 0.0
    if geometry.get("type") == "Polygon":
        return polygon_area(geometry.get("coordinates") or [])
    return 0.0


def points_bbox(points: Ring) -> list[float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def geometry_bbox(geometry: dict[str, Any] | None) -> list[float] | None:
    if not geometry or geometry.get("type") != "Polygon":
        return None
    points: Ring = []
    for ring in geometry.get("coordinates") or []:
        points.extend(ring)
    if not points:
        return None
    return points_bbox(points)


def is_single_polygon(geometry: dict[str, Any] | None) -> bool:
    return bool(geometry and geometry.get("type") == "Polygon")


def feature_has_multipolygon(feature: dict[str, Any]) -> bool:
    return (feature.get("geometry") or {}).get("type") == "MultiPolygon"


def is_white_fill(fill_hex: str | None) -> bool:
    if not fill_hex:
        return False
    return fill_hex.lower() in {"#ffffff", "#fff", "white"}


def is_full_page_bbox(
    bbox: list[float] | None,
    page_width: float,
    page_height: float,
    tolerance: float = 1.5,
) -> bool:
    if not bbox:
        return False
    x0, y0, x1, y1 = bbox
    return (
        abs(x0) <= tolerance
        and abs(y0) <= tolerance
        and abs(x1 - page_width) <= tolerance
        and abs(y1 - page_height) <= tolerance
    )


def validate_manual_polygon_edit(
    geom_before: dict[str, Any],
    geom_after: dict[str, Any],
    area_delta_review_threshold_pct: float = 25.0,
) -> GeometryValidation:
    errors: list[str] = []
    geometry_type = str((geom_after or {}).get("type"))
    is_single = geometry_type == "Polygon"
    if not is_single:
        errors.append("manual edits must produce a single Polygon")

    after_coords = (geom_after or {}).get("coordinates") or []
    after_outer = after_coords[0] if after_coords else []
    is_closed = is_closed_ring(after_outer)
    if not is_closed:
        errors.append("polygon exterior ring is not closed")

    area_before = geometry_area(geom_before)
    area_after = geometry_area(geom_after)
    is_valid = area_after > 0 and len(after_outer) >= 4 and is_closed
    if not is_valid:
        errors.append("polygon has no valid positive area")

    if area_before > 0:
        area_delta_pct = abs(area_after - area_before) / area_before * 100.0
    else:
        area_delta_pct = 100.0 if area_after > 0 else 0.0

    return GeometryValidation(
        geometry_type=geometry_type,
        is_single_polygon=is_single,
        is_closed_after=is_closed,
        is_valid_after=is_valid,
        area_before=area_before,
        area_after=area_after,
        area_delta_pct=area_delta_pct,
        review_note_required=area_delta_pct > area_delta_review_threshold_pct,
        errors=errors,
    )


def normalize_feature_properties(feature: dict[str, Any]) -> dict[str, Any]:
    props = feature.setdefault("properties", {})
    layer = props.get("LAYER") or props.get("layer")
    cls = props.get("CLASS") or props.get("class")
    typ = props.get("TYPE") or props.get("type")
    if layer and cls and not props.get("LAYER_CLASS"):
        props["LAYER_CLASS"] = f"{layer}.{cls}"
    if cls and typ and not props.get("class_type"):
        suffix = {"STAV": "1", "NAVRH": "2", "REZERVA": "3"}.get(str(typ).upper(), "0")
        props["class_type"] = f"{cls}.{suffix}"
    if "IS_CLOSED" not in props:
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates") or []
        props["IS_CLOSED"] = bool(geom.get("type") == "Polygon" and coords and is_closed_ring(coords[0]))
    return props

