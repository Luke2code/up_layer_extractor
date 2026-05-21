from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health_and_sample_kvetnice_regression() -> None:
    assert client.get("/api/health").json()["ok"] is True
    sample = client.get("/api/sample/kvetnice").json()
    assert sample["coordinate_system"] == "PDF_PAGE_POINTS_Y_DOWN_NO_CRS"
    assert len(sample["features"]) == 112
    assert all(feature["geometry"]["type"] == "Polygon" for feature in sample["features"])
    required = {"FID", "LAYER", "CLASS", "TYPE", "LAYER_CLASS", "class_type", "text_id", "IS_CLOSED"}
    for feature in sample["features"]:
      assert required <= set(feature["properties"])
    zmen = [feature for feature in sample["features"] if feature["properties"]["LAYER"] == "ZMEN"]
    assert zmen
    assert all(feature["properties"]["TYPE"] == "NAVRH" for feature in zmen)
    assert all(feature["properties"].get("has_fill_color") is False for feature in zmen)


def test_babice_fake_success_demo_is_diagnostic_only() -> None:
    result = client.get("/api/diagnostics/babice-failure-demo").json()
    assert result["classification_status"] == "diagnostic_only"
    assert result["selected_algorithm"] == "diagnostic_only_v1"
    assert result["features"] == []
    assert result["diagnostics"]["only_full_page_white_polygon"] is True


def test_definition_generation_and_approval_roundtrip() -> None:
    sample = client.get("/api/sample/kvetnice").json()
    result = client.post("/api/definitions/candidates", json={"feature_collection": sample}).json()
    assert result["vector_definitions"]
    assert result["text_definitions"]
    first = result["vector_definitions"][0]
    approved = client.post(
        "/api/definitions/approve",
        json={"candidate_id": first["candidate_id"], "kind": "vector", "approved_by": "pytest"},
    ).json()
    assert approved["definition_status"] == "approved"
    assert approved["approved_by"] == "pytest"


def test_manual_edit_and_annotation_roundtrip() -> None:
    square = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
    }
    adjusted = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [11, 0], [11, 10], [0, 10], [0, 0]]],
    }
    edit = client.post(
        "/api/manual/edits",
        json={
            "up_id": "pytest-up",
            "stg_polygon_id": "pytest-stg",
            "fid": 1,
            "edit_reason": "boundary adjustment",
            "geom_page_before": square,
            "geom_page_after": adjusted,
            "created_by": "pytest",
        },
    ).json()
    assert edit["manual_edit_id"]
    assert edit["is_valid_after"] is True

    annotation = client.post(
        "/api/manual/annotations",
        json={
            "up_id": "pytest-up",
            "stg_polygon_id": "pytest-stg",
            "annotation_type": "note",
            "note_text": "reviewed",
            "created_by": "pytest",
        },
    ).json()
    assert annotation["annotation_id"]
    assert annotation["note_text"] == "reviewed"


def test_remap_preview_api() -> None:
    result = client.post("/api/remap/preview", json={"LAYER": "RZVP", "CLASS": "BI", "TYPE": "STAV"}).json()
    assert result["proposed_layer_class"] == "RZVP.BI"
    assert result["proposed_class_type"] == "BI.1"
    assert result["requires_manual_review"] is False

