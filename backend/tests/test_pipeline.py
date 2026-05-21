from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.pipeline import (
    analyze_tessellation_fragments,
    build_legend_mapping_artifacts,
    build_visual_artifact_diagnostics,
    classify_evidence,
    classify_fragment_roles,
    detect_target_code,
    derive_legend_bbox,
    export_collection,
    feature_void_metrics,
    label_quality_fields,
    merge_tessellated_fill_features,
    parse_dash_pattern,
)


client = TestClient(app)


def test_classification_exact_code_mapping() -> None:
    result = classify_evidence(raw_layer="RZVP", raw_class="BI", raw_type="STAV")
    assert result["proposed_up_class"] == "BI"
    assert result["is_inscope_bydleni_related"] is True
    assert result["requires_review"] is True


def test_classification_synonym_mapping() -> None:
    result = classify_evidence(raw_layer=None, raw_class=None, raw_type="NAVRH", legend_label_candidate="smíšené obytné plochy")
    assert result["proposed_up_class"] == "S"
    assert result["is_inscope_bydleni_related"] is True
    assert result["confidence"] >= 0.8


def test_classification_code_mapping() -> None:
    result = classify_evidence(raw_layer=None, raw_class=None, raw_type="STAV", source_text_nearby="RI")
    assert result["proposed_up_class"] == "RI"
    assert result["rule_id"] == "text_label_target_scope_match"


def test_dash_pattern_lowers_confidence_and_requires_review() -> None:
    result = classify_evidence(raw_layer=None, raw_class=None, raw_type="STAV", source_text_nearby="BV", dash_pattern_normalized="4,2")
    assert result["proposed_up_class"] == "BV"
    assert result["requires_review"] is True
    assert result["evidence_dash_pattern"] is True


def test_solid_dash_patterns_do_not_count_as_dash() -> None:
    for raw in [None, "", [], "[] 0", "[] 0.0", "[0] 0", "0"]:
        dash_array, dash_phase, normalized = parse_dash_pattern(raw)
        assert dash_array == []
        assert dash_phase == 0.0
        assert normalized == "solid"
    result = classify_evidence(raw_layer=None, raw_class=None, raw_type="STAV", source_text_nearby="BI", dash_pattern_normalized="solid")
    assert result["evidence_dash_pattern"] is False


def test_target_code_detection_supports_kamenice_codes() -> None:
    assert detect_target_code("BU") == "BU"
    assert detect_target_code("SX") == "SX"
    assert detect_target_code("BX.c") == "BX.c"
    assert detect_target_code("BX p") == "BX.p"
    assert detect_target_code("BX-r") == "BX.r"


def test_legend_driven_mapping() -> None:
    result = classify_evidence(raw_layer=None, raw_class=None, raw_type="STAV", legend_label_candidate="bydlení individuální")
    assert result["proposed_up_class"] == "B"
    assert result["rule_id"] == "legend_label_target_scope_match"


def test_unknown_requires_review() -> None:
    result = classify_evidence(raw_layer=None, raw_class=None, raw_type=None, source_layer_name="technická infrastruktura")
    assert result["proposed_up_class"] == "UNMAPPED"
    assert result["requires_review"] is True


def test_conflicting_evidence_requires_review() -> None:
    result = classify_evidence(raw_layer=None, raw_class="BI", raw_type="STAV", legend_label_candidate="rekreace")
    assert result["rule_id"] == "conflicting_target_evidence"
    assert result["requires_review"] is True


def test_sample_is_enriched_with_pipeline_records() -> None:
    sample = client.get("/api/sample/kvetnice").json()
    assert sample["run_id"].startswith("run-")
    assert sample["collection_id"].startswith("collection-")
    assert sample["source_type"] == "geojson"
    assert sample["feature_count"] == len(sample["features"])
    assert sample["vector_definitions"]
    assert sample["classification_proposals"]
    assert sample["pipeline_traces"]
    assert sample["sample_legend_crop_available"] is False
    assert sample["legend_crop_source"] == "unavailable_geojson_only_sample"
    assert "GeoJSON-only" in sample["legend_unavailable_reason"]


def test_geojson_upload_is_enriched() -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "f1",
                "properties": {"FID": 1, "LAYER": "RZVP", "CLASS": "BI", "TYPE": "STAV", "IS_CLOSED": True},
                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]},
            }
        ],
    }
    response = client.post(
        "/api/extract_upload",
        files={"file": ("sample.geojson", json.dumps(payload).encode("utf-8"), "application/geo+json")},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["source_type"] == "geojson"
    assert result["vector_def_count"] == 1


def test_pdf_upload_has_detection_and_specs(tmp_path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf = tmp_path / "filled_path.pdf"
    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    page.insert_text((12, 18), "BI", fontsize=8)
    shape = page.new_shape()
    shape.draw_line((10, 10), (90, 10))
    shape.draw_line((90, 10), (50, 80))
    shape.draw_line((50, 80), (10, 10))
    shape.finish(fill=(1, 0, 0), color=None)
    shape.commit()
    doc.save(pdf)
    doc.close()

    response = client.post(
        "/api/extract_upload",
        files={"file": ("filled_path.pdf", pdf.read_bytes(), "application/pdf")},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["source_detection"]["source_type"] == "vector_pdf"
    assert result["run_id"].startswith("run-")
    assert result["vector_definitions"]
    assert result["text_definitions"]
    assert result["classification_proposals"]
    assert result["pipeline_traces"]
    assert result["plan_snapshot_available"] is True
    assert result["plan_snapshot_url"].endswith(".png")
    assert result["plan_snapshot_transform"]["page_coordinate_y_axis"] == "down"


def test_label_quality_hides_garbled_text() -> None:
    fields = label_quality_fields('%<"/(1Ě', "BU")
    assert fields["label_text_status"] == "agent_proposed"
    assert fields["label_text_display"] == "BYDLENÍ VŠEOBECNÉ"
    assert fields["label_text_raw"] != fields["label_text_display"]


def test_feature_void_metrics_flags_small_triangular_hole() -> None:
    feature = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[0, 0], [20, 0], [20, 20], [0, 20], [0, 0]],
                [[1, 1], [3, 1], [2, 3], [1, 1]],
            ],
        },
    }
    metrics = feature_void_metrics(feature)
    assert metrics["triangular_void_count"] == 1
    assert metrics["small_void_count"] == 1
    assert metrics["void_requires_review_count"] == 2
    assert metrics["void_matches_original_plan"] == "requires_plan_visual_review"


def test_export_collection_jsonl_and_csv() -> None:
    sample = client.get("/api/sample/kvetnice").json()
    jsonl = client.post("/api/exports/pipeline_traces", json={"feature_collection": sample})
    assert jsonl.status_code == 200
    assert json.loads(jsonl.text.splitlines()[0])["run_id"] == sample["run_id"]

    csv_response = client.post("/api/exports/vector_definitions", json={"feature_collection": sample})
    assert csv_response.status_code == 200
    assert "vector_def_id" in csv_response.text.splitlines()[0]


def test_export_collection_rejects_unknown_kind() -> None:
    with pytest.raises(KeyError):
        export_collection({"type": "FeatureCollection", "features": []}, "missing")


def test_tessellated_fragment_detector_and_merge_on_synthetic_stripes() -> None:
    features = []
    fid = 1
    for row in range(100):
        for col in range(60):
            x = float(col)
            y = float(row)
            for coords in [
                [[[x, y], [x + 1.0, y], [x + 1.0, y + 1.0], [x, y]]],
                [[[x, y], [x + 1.0, y + 1.0], [x, y + 1.0], [x, y]]],
            ]:
                features.append(
                    {
                        "type": "Feature",
                        "id": f"candidate-{fid:05d}",
                        "properties": {
                            "FID": fid,
                            "source_style_hex": "#ff0000",
                            "source_region_class": "map_body_region",
                            "bbox_page_pt": [x, y, x + 1.0, y + 1.0],
                        },
                        "geometry": {"type": "Polygon", "coordinates": coords},
                    }
                )
                fid += 1
    metrics = analyze_tessellation_fragments(features, page_width=200, page_height=200)
    assert metrics["tessellated_fill_detected"] is True
    features.append(
        {
            "type": "Feature",
            "id": "text-mask",
            "properties": {
                "FID": 999999,
                "source_style_hex": "#ffffff",
                "source_region_class": "map_body_region",
                "bbox_page_pt": [5.0, 5.0, 8.0, 8.0],
            },
            "geometry": {"type": "Polygon", "coordinates": [[[5.0, 5.0], [8.0, 5.0], [8.0, 8.0], [5.0, 8.0], [5.0, 5.0]]]},
        }
    )
    role_stats = classify_fragment_roles(features, page_width=200, page_height=200, tessellation=metrics)
    assert role_stats["fragment_role_counts"]["text_mask_fragment"] == 1
    merged, stats, errors = merge_tessellated_fill_features(
        features,
        run_id="run-test",
        collection_id="collection-test",
        source_url="test",
        source_pdf="synthetic.pdf",
        source_fingerprint="f" * 64,
        page_number=1,
        tessellation=metrics,
    )
    assert not errors
    assert stats["raw_features_are_debug_only"] is True
    assert stats["raw_skipped_by_fragment_role"]["text_mask_fragment"] == 1
    assert len(merged) < len(features)
    assert {feature["properties"]["merge_algorithm"] for feature in merged} == {"vector_tessellated_fill_merge_v1"}
    artifact_stats = build_visual_artifact_diagnostics(features, merged)
    assert artifact_stats["white_fill_fragment_count"] == 1
    assert artifact_stats["trusted_white_or_background_feature_count"] == 0


def test_target_left_legend_bbox_and_symbol_split() -> None:
    text_specs = [
        {"text_def_id": "t1", "raw_text": "BU", "matched_code_candidate": "BU", "bbox_page_pt": [154, 1276, 171, 1288]},
        {"text_def_id": "t2", "raw_text": "BU", "matched_code_candidate": "BU", "bbox_page_pt": [225, 1276, 242, 1288]},
        {"text_def_id": "t3", "raw_text": "BI", "matched_code_candidate": "BI", "bbox_page_pt": [155, 1315, 170, 1327]},
        {"text_def_id": "t4", "raw_text": "BI", "matched_code_candidate": "BI", "bbox_page_pt": [226, 1315, 241, 1327]},
        {"text_def_id": "t5", "raw_text": "BH", "matched_code_candidate": "BH", "bbox_page_pt": [154, 1355, 171, 1367]},
        {"text_def_id": "t6", "raw_text": "BX.c", "matched_code_candidate": "BX.c", "bbox_page_pt": [149, 1395, 176, 1407]},
        {"text_def_id": "t7", "raw_text": "BX.c", "matched_code_candidate": "BX.c", "bbox_page_pt": [220, 1395, 247, 1407]},
        {"text_def_id": "t8", "raw_text": "RI", "matched_code_candidate": "RI", "bbox_page_pt": [156, 1514, 168, 1526]},
        {"text_def_id": "t9", "raw_text": "SV", "matched_code_candidate": "SV", "bbox_page_pt": [155, 2030, 170, 2042]},
        {"text_def_id": "t10", "raw_text": "SX", "matched_code_candidate": "SX", "bbox_page_pt": [155, 2109, 170, 2121]},
        {"text_def_id": "l1", "raw_text": "BYDLENI VSEOBECNE", "matched_code_candidate": None, "bbox_page_pt": [346, 1275, 500, 1289]},
        {"text_def_id": "l2", "raw_text": "BYDLENI INDIVIDUALNI", "matched_code_candidate": None, "bbox_page_pt": [346, 1315, 500, 1329]},
    ]
    detection = derive_legend_bbox(text_specs=text_specs, page_width=5051, page_height=3019)
    assert detection["strategy"] == "target_left_legend_code_cluster_v1"
    legend_bbox = detection["bbox"]
    crop = {
        "legend_crop_id": "legend-autocrop-0001",
        "image_artifact_path_or_url": "/tmp/legend.png",
        "image_width_px": 960,
        "image_height_px": 1500,
        "crop_bbox_page_pt": legend_bbox,
        "page_to_image_transform": {
            "page_to_image_scale_x": 1.5,
            "page_to_image_scale_y": 1.5,
            "page_to_image_offset_x": -legend_bbox[0] * 1.5,
            "page_to_image_offset_y": -legend_bbox[1] * 1.5,
        },
    }
    rows, items, symbols, vector_defs, stats, corrections = build_legend_mapping_artifacts(
        run_id="run-test",
        collection_id="collection-test",
        source_pdf="synthetic.pdf",
        source_fingerprint="f" * 64,
        text_specs=text_specs,
        raw_features=[],
        legend_bbox=legend_bbox,
        legend_crops=[crop],
        page_number=1,
    )
    assert rows
    assert items
    assert symbols
    assert stats["two_row_vector_def_split_count"] >= 2
    assert stats["missing_expected_symbol_count"] >= 1
    assert corrections
    assert {row["class_type_id"] for row in vector_defs if row["code_text"] == "BU"} == {1, 2}
    assert not [row for row in vector_defs if row["symbol_bbox_page_pt"] is None]
