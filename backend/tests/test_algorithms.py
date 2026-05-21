from __future__ import annotations

import pytest

from backend.app.algorithms import (
    ALGORITHM_REGISTRY,
    choose_algorithm,
    diagnostics_from_drawings,
    extract_vector_candidates,
    normalize_url,
    _polygons_from_rings,
    _rings_from_path_items,
)


class Rect:
    x0 = 0
    y0 = 0
    x1 = 100
    y1 = 100


class Point:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y


def test_algorithm_registry_contract() -> None:
    assert set(ALGORITHM_REGISTRY) == {
        "vector_fill_style_polygon_v1",
        "vector_text_boundary_topology_v1",
        "raster_style_segmentation_v1",
        "diagnostic_only_v1",
    }
    for descriptor in ALGORITHM_REGISTRY.values():
        assert descriptor.algorithm_id
        assert descriptor.required_pdf_capabilities
        assert descriptor.output_contract
        assert descriptor.failure_mode


def test_full_page_white_background_routes_to_diagnostic_only() -> None:
    diagnostics = diagnostics_from_drawings(
        page_count=1,
        page_width=100,
        page_height=100,
        drawings=[{"fill": (1.0, 1.0, 1.0), "items": [("re", Rect())]}],
        images_count=0,
        text_label_candidates=0,
        raster_image_coverage_ratio=0,
    )
    assert diagnostics["only_full_page_white_polygon"] is True
    assert choose_algorithm(diagnostics) == "diagnostic_only_v1"


def test_non_background_fill_routes_to_fill_algorithm() -> None:
    diagnostics = diagnostics_from_drawings(
        page_count=1,
        page_width=100,
        page_height=100,
        drawings=[{"fill": (1.0, 0.0, 0.0), "items": [("re", Rect())]}],
        images_count=0,
        text_label_candidates=0,
        raster_image_coverage_ratio=0,
    )
    assert diagnostics["only_full_page_white_polygon"] is False
    assert choose_algorithm(diagnostics) == "vector_fill_style_polygon_v1"


def test_url_normalization_rejects_non_http() -> None:
    with pytest.raises(ValueError):
        normalize_url("file:///tmp/test.pdf")
    assert normalize_url("https://example.test/a b.pdf").endswith("/a%20b.pdf")


def test_filled_line_path_items_are_polygonized() -> None:
    rings = _rings_from_path_items(
        [
            ("l", Point(10, 10), Point(90, 10)),
            ("l", Point(90, 10), Point(90, 80)),
            ("l", Point(90, 80), Point(10, 10)),
        ]
    )
    assert rings == [[[10.0, 10.0], [90.0, 10.0], [90.0, 80.0], [10.0, 10.0]]]


def test_filled_curve_path_items_are_flattened_and_closed() -> None:
    rings = _rings_from_path_items(
        [
            ("c", Point(10, 10), Point(30, 0), Point(70, 0), Point(90, 10)),
            ("l", Point(90, 10), Point(10, 10)),
        ]
    )
    assert len(rings) == 1
    assert len(rings[0]) > 4
    assert rings[0][0] == rings[0][-1]


def test_nested_path_rings_become_polygon_with_hole() -> None:
    outer = [[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0], [0.0, 0.0]]
    hole = [[25.0, 25.0], [75.0, 25.0], [75.0, 75.0], [25.0, 75.0], [25.0, 25.0]]
    polygons = _polygons_from_rings([outer, hole])
    assert polygons == [[outer, hole]]


def test_invalid_hole_group_falls_back_to_outer_ring() -> None:
    outer = [[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0], [0.0, 0.0]]
    left_hole = [[1.0, 1.0], [70.0, 1.0], [70.0, 99.0], [1.0, 99.0], [1.0, 1.0]]
    right_hole = [[30.0, 1.0], [99.0, 1.0], [99.0, 99.0], [30.0, 99.0], [30.0, 1.0]]
    polygons = _polygons_from_rings([outer, left_hole, right_hole])
    assert polygons == [[outer]]


def test_extract_vector_candidates_handles_non_rect_filled_pdf(tmp_path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf = tmp_path / "filled_path.pdf"
    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    shape = page.new_shape()
    shape.draw_line((10, 10), (90, 10))
    shape.draw_line((90, 10), (50, 80))
    shape.draw_line((50, 80), (10, 10))
    shape.finish(fill=(1, 0, 0), color=None)
    shape.commit()
    doc.save(pdf)
    doc.close()

    collection = extract_vector_candidates(pdf)

    assert collection["selected_algorithm"] == "vector_fill_style_polygon_v1"
    assert len(collection["features"]) == 1
    assert collection["features"][0]["geometry"]["type"] == "Polygon"
    assert collection["features"][0]["properties"]["source_path_item_type_counts"]["l"] == 3
