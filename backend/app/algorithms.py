from __future__ import annotations

import hashlib
import json
import math
import tempfile
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests
from fastapi import HTTPException

from .geometry import close_ring, is_full_page_bbox, is_white_fill, points_bbox, polygon_area, ring_area
from .pipeline import enrich_geojson_collection, finalize_pdf_collection

try:
    import fitz
except Exception:  # pragma: no cover - covered by runtime dependency validation.
    fitz = None


@dataclass(frozen=True)
class AlgorithmDescriptor:
    algorithm_id: str
    applicable_diagnostics: list[str]
    required_pdf_capabilities: list[str]
    output_contract: str
    confidence_rules: list[str]
    failure_mode: str

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


ALGORITHM_REGISTRY: dict[str, AlgorithmDescriptor] = {
    "vector_fill_style_polygon_v1": AlgorithmDescriptor(
        algorithm_id="vector_fill_style_polygon_v1",
        applicable_diagnostics=["non-background fill styles", "closed vector paths"],
        required_pdf_capabilities=["page.get_drawings fill/path objects"],
        output_contract="single Polygon candidates in PDF page coordinates",
        confidence_rules=["exclude full-page white background", "style definitions required before trusted output"],
        failure_mode="route to diagnostic_only when only background fills are present",
    ),
    "vector_text_boundary_topology_v1": AlgorithmDescriptor(
        algorithm_id="vector_text_boundary_topology_v1",
        applicable_diagnostics=["text labels", "boundary strokes without fill"],
        required_pdf_capabilities=["page.get_text dict/rawdict", "stroke paths"],
        output_contract="single Polygon candidates with text assignment diagnostics",
        confidence_rules=["requires text definition and boundary topology evidence"],
        failure_mode="review_required when topology cannot be closed",
    ),
    "raster_style_segmentation_v1": AlgorithmDescriptor(
        algorithm_id="raster_style_segmentation_v1",
        applicable_diagnostics=["raster/image coverage", "weak vector style evidence"],
        required_pdf_capabilities=["page raster pixmap or source image"],
        output_contract="source-raster mask candidates labeled as raster-derived",
        confidence_rules=["must declare validation_source independent of output footprint"],
        failure_mode="diagnostic_only until segmentation profile is available",
    ),
    "diagnostic_only_v1": AlgorithmDescriptor(
        algorithm_id="diagnostic_only_v1",
        applicable_diagnostics=["unsafe extraction", "only full-page white background", "no matching algorithm"],
        required_pdf_capabilities=["diagnostic metadata only"],
        output_contract="no trusted features; diagnostics explain failure mode",
        confidence_rules=["classification_status=diagnostic_only"],
        failure_mode="no extraction candidates are emitted",
    ),
}


def normalize_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme not in {"http", "https"}:
        raise ValueError("Only http/https source URLs are supported")
    path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/%")
    query = urllib.parse.quote(urllib.parse.unquote(parts.query), safe="=&?/%:+")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def download_pdf(url: str, out_dir: Path) -> Path:
    normalized = normalize_url(url)
    out = out_dir / (hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16] + ".pdf")
    headers = {"User-Agent": "UPLayerExtractor/1.0 (+server-side PDF fetch)"}
    with requests.get(normalized, headers=headers, timeout=60, stream=True) as response:
        response.raise_for_status()
        ctype = response.headers.get("content-type", "").lower()
        if "pdf" not in ctype and not normalized.lower().endswith(".pdf"):
            raise HTTPException(415, f"URL did not look like PDF: content-type={ctype!r}")
        with out.open("wb") as handle:
            for chunk in response.iter_content(1024 * 256):
                if chunk:
                    handle.write(chunk)
    if out.stat().st_size < 1024:
        raise HTTPException(422, "Downloaded PDF is suspiciously small")
    return out


def style_hex(rgb: Any) -> str | None:
    if not rgb:
        return None
    try:
        r, g, b = rgb[:3]
        return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))
    except Exception:
        return None


def page_score(page: Any) -> int:
    upper = (page.get_text("text") or "").upper()
    score = 0
    for token in ["HLAVNÍ VÝKRES", "HLAVNI VYKRES", "ÚPLNÉ ZNĚNÍ", "UPLNE ZNENI", "Z12"]:
        if token in upper:
            score += 10
    try:
        score += min(len(page.get_drawings()) // 100, 10)
    except Exception:
        pass
    return score


def _rect_points(rect: Any) -> list[list[float]]:
    return [
        [float(rect.x0), float(rect.y0)],
        [float(rect.x1), float(rect.y0)],
        [float(rect.x1), float(rect.y1)],
        [float(rect.x0), float(rect.y1)],
        [float(rect.x0), float(rect.y0)],
    ]


def _point_xy(point: Any) -> list[float]:
    return [float(point.x), float(point.y)]


def _points_close(left: list[float], right: list[float], tolerance: float = 0.05) -> bool:
    return abs(left[0] - right[0]) <= tolerance and abs(left[1] - right[1]) <= tolerance


def _dedupe_consecutive_points(points: list[list[float]]) -> list[list[float]]:
    deduped: list[list[float]] = []
    for point in points:
        if not deduped or not _points_close(deduped[-1], point):
            deduped.append(point)
    if len(deduped) > 1 and _points_close(deduped[0], deduped[-1]):
        deduped[-1] = [deduped[0][0], deduped[0][1]]
    return deduped


def _cubic_bezier_points(
    p0: list[float],
    p1: list[float],
    p2: list[float],
    p3: list[float],
) -> list[list[float]]:
    control_length = (
        math.dist(p0, p1)
        + math.dist(p1, p2)
        + math.dist(p2, p3)
    )
    chord_length = max(math.dist(p0, p3), 1e-6)
    segments = max(4, min(16, int(control_length / chord_length * 4)))
    points: list[list[float]] = []
    for index in range(1, segments + 1):
        t = index / segments
        mt = 1 - t
        points.append(
            [
                mt**3 * p0[0]
                + 3 * mt * mt * t * p1[0]
                + 3 * mt * t * t * p2[0]
                + t**3 * p3[0],
                mt**3 * p0[1]
                + 3 * mt * mt * t * p1[1]
                + 3 * mt * t * t * p2[1]
                + t**3 * p3[1],
            ]
        )
    return points


def _quad_points(quad: Any) -> list[list[float]]:
    try:
        points = [_point_xy(quad.ul), _point_xy(quad.ur), _point_xy(quad.lr), _point_xy(quad.ll)]
    except Exception:
        points = [_point_xy(point) for point in quad]
    return close_ring(points)


def _valid_ring(points: list[list[float]], minimum_area: float = 0.01) -> list[list[float]] | None:
    ring = _dedupe_consecutive_points(close_ring(points))
    if len(ring) < 4 or abs(ring_area(ring)) <= minimum_area:
        return None
    return ring


def _rings_from_path_items(items: list[Any]) -> list[list[list[float]]]:
    rings: list[list[list[float]]] = []
    current: list[list[float]] = []

    def flush_current() -> None:
        nonlocal current
        ring = _valid_ring(current)
        if ring:
            rings.append(ring)
        current = []

    for item in items:
        if not item:
            continue
        op = item[0]
        if op == "re":
            if current:
                flush_current()
            ring = _valid_ring(_rect_points(item[1]))
            if ring:
                rings.append(ring)
            continue
        if op == "qu":
            if current:
                flush_current()
            ring = _valid_ring(_quad_points(item[1]))
            if ring:
                rings.append(ring)
            continue
        if op == "l":
            start = _point_xy(item[1])
            end = _point_xy(item[2])
            if not current:
                current = [start, end]
            elif _points_close(current[-1], start):
                current.append(end)
            elif _points_close(current[-1], end):
                current.append(start)
            else:
                flush_current()
                current = [start, end]
            continue
        if op == "c":
            p0 = _point_xy(item[1])
            p1 = _point_xy(item[2])
            p2 = _point_xy(item[3])
            p3 = _point_xy(item[4])
            if not current:
                current = [p0]
            elif not _points_close(current[-1], p0):
                flush_current()
                current = [p0]
            current.extend(_cubic_bezier_points(p0, p1, p2, p3))
            continue

    if current:
        flush_current()
    return rings


def _point_in_ring(point: list[float], ring: list[list[float]]) -> bool:
    x, y = point
    inside = False
    closed = close_ring(ring)
    for left, right in zip(closed, closed[1:]):
        y_crosses = (left[1] > y) != (right[1] > y)
        if not y_crosses:
            continue
        x_intersection = (right[0] - left[0]) * (y - left[1]) / ((right[1] - left[1]) or 1e-12) + left[0]
        if x < x_intersection:
            inside = not inside
    return inside


def _polygons_from_rings(rings: list[list[list[float]]]) -> list[list[list[list[float]]]]:
    if not rings:
        return []
    ring_info = [
        {
            "index": index,
            "ring": ring,
            "area": abs(ring_area(ring)),
            "sample": ring[0],
        }
        for index, ring in enumerate(rings)
    ]
    for info in ring_info:
        containing = [
            other
            for other in ring_info
            if other["index"] != info["index"]
            and other["area"] > info["area"]
            and _point_in_ring(info["sample"], other["ring"])
        ]
        info["depth"] = len(containing)
        info["parent"] = min(containing, key=lambda item: item["area"])["index"] if containing else None

    polygons: dict[int, list[list[list[float]]]] = {
        info["index"]: [info["ring"]]
        for info in ring_info
        if int(info["depth"]) % 2 == 0
    }
    for info in ring_info:
        if int(info["depth"]) % 2 == 0:
            continue
        parent = info["parent"]
        while parent is not None and parent not in polygons:
            parent_info = next((candidate for candidate in ring_info if candidate["index"] == parent), None)
            parent = parent_info["parent"] if parent_info else None
        if parent in polygons:
            polygons[parent].append(info["ring"])
        else:
            polygons[info["index"]] = [info["ring"]]

    normalized: list[list[list[list[float]]]] = []
    for coordinates in polygons.values():
        if polygon_area(coordinates) > 0.01:
            normalized.append(coordinates)
        elif coordinates and abs(ring_area(coordinates[0])) > 0.01:
            normalized.append([coordinates[0]])
    return normalized


def _path_item_type_counts(items: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        if item:
            counts[str(item[0])] = counts.get(str(item[0]), 0) + 1
    return counts


def diagnostics_from_drawings(
    *,
    page_count: int,
    page_width: float,
    page_height: float,
    drawings: list[dict[str, Any]],
    images_count: int,
    text_label_candidates: int,
    raster_image_coverage_ratio: float,
) -> dict[str, Any]:
    fill_style_counts: dict[str, int] = {}
    stroke_style_counts: dict[str, int] = {}
    background_full_page_count = 0

    for draw in drawings:
        fill = style_hex(draw.get("fill"))
        stroke = style_hex(draw.get("color"))
        if fill:
            fill_style_counts[fill] = fill_style_counts.get(fill, 0) + 1
        if stroke:
            stroke_style_counts[stroke] = stroke_style_counts.get(stroke, 0) + 1

        for item in draw.get("items", []):
            if not item or item[0] != "re":
                continue
            bbox = points_bbox(_rect_points(item[1]))
            if is_white_fill(fill) and is_full_page_bbox(bbox, page_width, page_height):
                background_full_page_count += 1

    non_background_fill_count = sum(
        count for fill, count in fill_style_counts.items() if not is_white_fill(fill)
    )
    only_full_page_white_polygon = (
        background_full_page_count > 0
        and non_background_fill_count == 0
        and len(fill_style_counts) <= 1
    )
    return {
        "page_count": page_count,
        "drawing_count": len(drawings),
        "image_count": images_count,
        "fill_style_counts": fill_style_counts,
        "stroke_style_counts": stroke_style_counts,
        "background_full_page_count": background_full_page_count,
        "text_label_candidates": text_label_candidates,
        "raster_image_coverage_ratio": raster_image_coverage_ratio,
        "legend_candidate_presence": bool(fill_style_counts or text_label_candidates),
        "only_full_page_white_polygon": only_full_page_white_polygon,
    }


def choose_algorithm(diagnostics: dict[str, Any]) -> str:
    if diagnostics.get("only_full_page_white_polygon"):
        return "diagnostic_only_v1"
    fills = diagnostics.get("fill_style_counts") or {}
    non_background_fills = [key for key in fills if not is_white_fill(key)]
    if non_background_fills:
        return "vector_fill_style_polygon_v1"
    if diagnostics.get("raster_image_coverage_ratio", 0) >= 0.45 or diagnostics.get("image_count", 0) > 0:
        return "raster_style_segmentation_v1"
    if diagnostics.get("text_label_candidates", 0) > 0 or diagnostics.get("stroke_style_counts"):
        return "vector_text_boundary_topology_v1"
    return "diagnostic_only_v1"


def diagnose_pdf(pdf_path: Path) -> tuple[int, Any, list[dict[str, Any]], dict[str, Any]]:
    if fitz is None:
        raise HTTPException(500, "PyMuPDF is not installed")
    doc = fitz.open(pdf_path)
    if doc.page_count == 0:
        raise HTTPException(422, "PDF has no pages")

    scored = sorted([(page_score(doc[i]), i) for i in range(doc.page_count)], reverse=True)
    page_index = scored[0][1]
    page = doc[page_index]
    drawings = page.get_drawings()
    text = page.get_text("text") or ""
    image_count = len(page.get_images(full=True))
    raster_area = 0.0
    for image in page.get_images(full=True):
        try:
            width = float(image[2])
            height = float(image[3])
            raster_area += width * height
        except Exception:
            continue
    page_area = max(float(page.rect.width) * float(page.rect.height), 1.0)
    diagnostics = diagnostics_from_drawings(
        page_count=doc.page_count,
        page_width=float(page.rect.width),
        page_height=float(page.rect.height),
        drawings=drawings,
        images_count=image_count,
        text_label_candidates=len([token for token in text.split() if token[:1] in {"Z", "P", "K"}]),
        raster_image_coverage_ratio=min(1.0, raster_area / page_area),
    )
    return page_index, page, drawings, diagnostics


def diagnostic_failure_collection(
    *,
    name: str,
    source_url: str | None,
    diagnostics: dict[str, Any],
    selected_algorithm: str = "diagnostic_only_v1",
) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "name": name,
        "source_url": source_url,
        "coordinate_system": "PDF_PAGE_POINTS_Y_DOWN_NO_CRS",
        "classification_status": "diagnostic_only",
        "selected_algorithm": selected_algorithm,
        "diagnostics": diagnostics,
        "features": [],
        "warning": "No trusted extraction candidates emitted. Diagnostics must be reviewed before routing to another algorithm.",
    }


def extract_vector_candidates(pdf_path: Path, source_url: str | None = None) -> dict[str, Any]:
    page_index, page, drawings, diagnostics = diagnose_pdf(pdf_path)
    selected_algorithm = choose_algorithm(diagnostics)

    if selected_algorithm != "vector_fill_style_polygon_v1":
        status = "diagnostic_only" if selected_algorithm == "diagnostic_only_v1" else "algorithm_routed_pending_profile"
        fc = diagnostic_failure_collection(
            name=f"{pdf_path.stem}_diagnostics",
            source_url=source_url,
            diagnostics=diagnostics,
            selected_algorithm=selected_algorithm,
        )
        fc["classification_status"] = status
        return finalize_pdf_collection(
            fc,
            pdf_path=pdf_path,
            source_url=source_url,
            page=page,
            drawings=drawings,
            diagnostics=diagnostics,
            page_number=page_index + 1,
            selected_algorithm=selected_algorithm,
        )

    features: list[dict[str, Any]] = []
    raw_objects: list[dict[str, Any]] = []
    fid = 1
    pdf_sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    extraction_stats = {
        "filled_drawings_seen": 0,
        "filled_drawings_without_polygon": 0,
        "background_rings_skipped": 0,
        "path_polygons_extracted": 0,
        "rect_polygons_extracted": 0,
        "curve_items_flattened": 0,
        "quad_polygons_extracted": 0,
    }
    for drawing_index, draw in enumerate(drawings):
        fill_hex = style_hex(draw.get("fill"))
        stroke_hex = style_hex(draw.get("color"))
        items = draw.get("items", [])
        item_type_counts = _path_item_type_counts(items)
        if fill_hex:
            extraction_stats["filled_drawings_seen"] += 1
        polygons = _polygons_from_rings(_rings_from_path_items(items)) if fill_hex else []
        if fill_hex and not polygons:
            extraction_stats["filled_drawings_without_polygon"] += 1
        if fill_hex and len(raw_objects) < 500:
            raw_objects.append(
                {
                    "drawing_index": drawing_index,
                    "geom_type_raw": "path",
                    "fill_hex": fill_hex,
                    "stroke_hex": stroke_hex,
                    "stroke_width": draw.get("width"),
                    "dash_array": draw.get("dashes"),
                    "fill_opacity": draw.get("fill_opacity"),
                    "stroke_opacity": draw.get("stroke_opacity"),
                    "even_odd": draw.get("even_odd"),
                    "source_layer_name": draw.get("layer"),
                    "path_item_type_counts": item_type_counts,
                    "polygon_count": len(polygons),
                    "bbox_page": [
                        float(draw["rect"].x0),
                        float(draw["rect"].y0),
                        float(draw["rect"].x1),
                        float(draw["rect"].y1),
                    ]
                    if draw.get("rect")
                    else None,
                }
            )
        extraction_stats["curve_items_flattened"] += item_type_counts.get("c", 0)
        extraction_stats["quad_polygons_extracted"] += item_type_counts.get("qu", 0)

        for polygon_index, coordinates in enumerate(polygons):
            exterior = coordinates[0]
            bbox = points_bbox(exterior)
            is_background = is_white_fill(fill_hex) and is_full_page_bbox(bbox, page.rect.width, page.rect.height)
            if is_background:
                extraction_stats["background_rings_skipped"] += 1
                continue
            if item_type_counts and set(item_type_counts) <= {"re"}:
                extraction_stats["rect_polygons_extracted"] += 1
            else:
                extraction_stats["path_polygons_extracted"] += 1
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
                "source_style_hex": fill_hex,
                "source_stroke_hex": stroke_hex,
                "source_fill_opacity": draw.get("fill_opacity"),
                "source_stroke_opacity": draw.get("stroke_opacity"),
                "source_layer_name": draw.get("layer"),
                "source_drawing_index": drawing_index,
                "source_subpath_index": polygon_index,
                "source_path_item_type_counts": item_type_counts,
                "classification_status": "candidate_requires_legend_or_profile_mapping",
                "source_url": source_url,
                "source_pdf": pdf_path.name,
                "source_pdf_sha256": pdf_sha256,
                "page": page_index + 1,
                "bbox_page_pt": bbox,
                "component_area_page_pt2": polygon_area(coordinates),
            }
            features.append(
                {
                    "type": "Feature",
                    "id": f"candidate-{fid:04d}",
                    "properties": props,
                    "geometry": {"type": "Polygon", "coordinates": coordinates},
                }
            )
            fid += 1

    if not features:
        fc = diagnostic_failure_collection(
            name=f"{pdf_path.stem}_diagnostics",
            source_url=source_url,
            diagnostics={**diagnostics, "raw_objects": raw_objects[:250], "extraction_stats": extraction_stats},
            selected_algorithm=selected_algorithm,
        )
        return finalize_pdf_collection(
            fc,
            pdf_path=pdf_path,
            source_url=source_url,
            page=page,
            drawings=drawings,
            diagnostics=diagnostics,
            page_number=page_index + 1,
            selected_algorithm=selected_algorithm,
        )

    fc = {
        "type": "FeatureCollection",
        "name": f"{pdf_path.stem}_vector_candidates_pagecoords",
        "source_url": source_url,
        "coordinate_system": "PDF_PAGE_POINTS_Y_DOWN_NO_CRS",
        "page_width_pt": float(page.rect.width),
        "page_height_pt": float(page.rect.height),
        "selected_page": page_index + 1,
        "page_count": diagnostics["page_count"],
        "selected_algorithm": selected_algorithm,
        "classification_status": "candidate_requires_legend_or_profile_mapping",
        "diagnostics": {**diagnostics, "extraction_stats": extraction_stats},
        "raw_objects": raw_objects[:500],
        "features": features,
        "warning": "Candidate extraction only. Do not treat as final classification until definitions and remapping are approved.",
    }
    return finalize_pdf_collection(
        fc,
        pdf_path=pdf_path,
        source_url=source_url,
        page=page,
        drawings=drawings,
        diagnostics=diagnostics,
        page_number=page_index + 1,
        selected_algorithm=selected_algorithm,
    )


def extract_url_to_feature_collection(url: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        normalized = normalize_url(url)
        headers = {"User-Agent": "UPLayerExtractor/1.0 (+server-side source fetch)"}
        response = requests.get(normalized, headers=headers, timeout=60)
        response.raise_for_status()
        ctype = response.headers.get("content-type", "").lower()
        lower_url = normalized.lower()
        if "json" in ctype or lower_url.endswith(".geojson") or lower_url.endswith(".json"):
            collection = response.json()
            if collection.get("type") != "FeatureCollection":
                raise HTTPException(415, "URL JSON is not a GeoJSON FeatureCollection")
            return enrich_geojson_collection(
                collection,
                source_filename=Path(urllib.parse.urlsplit(normalized).path).name or "remote.geojson",
                source_url=url,
                source_origin="geojson_url",
            )

        if "pdf" not in ctype and not lower_url.endswith(".pdf") and "original=" not in lower_url:
            try:
                collection = json.loads(response.text)
                if collection.get("type") == "FeatureCollection":
                    return enrich_geojson_collection(
                        collection,
                        source_filename=Path(urllib.parse.urlsplit(normalized).path).name or "remote.geojson",
                        source_url=url,
                        source_origin="geojson_url",
                    )
            except Exception:
                pass
            raise HTTPException(415, f"URL did not look like PDF or GeoJSON: content-type={ctype!r}")

        pdf = Path(tmp) / (hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16] + ".pdf")
        pdf.write_bytes(response.content)
        if pdf.stat().st_size < 1024:
            raise HTTPException(422, "Downloaded PDF is suspiciously small")
        return extract_vector_candidates(pdf, source_url=url)
