from __future__ import annotations

import re
from pathlib import Path


SQL = (Path(__file__).resolve().parents[2] / "db" / "migrations" / "001_init_up_layer_extractor.sql").read_text(encoding="utf-8")


def test_only_allowed_schemas_created() -> None:
    created = set(re.findall(r"CREATE\s+SCHEMA\s+IF\s+NOT\s+EXISTS\s+([a-z_]+)", SQL, re.I))
    assert created == {"up_import", "up_stg", "up_manual", "up_core", "up_api"}


def test_required_tables_and_views_present() -> None:
    for table in [
        "up_core.up_def",
        "up_core.up_type_def",
        "up_import.vector_import",
        "up_import.vector_def",
        "up_import.up_text_def",
        "up_stg.vector_stg_candidates",
        "up_stg.vector_stg_single_polygon",
        "up_stg.vector_stg_text_assignment",
        "up_stg.vector_stg_residual",
        "up_manual.vector_review",
        "up_manual.polygon_edit_session",
        "up_manual.polygon_annotation",
        "up_core.vector_output",
        "up_import.class_remap_config",
        "up_stg.class_remap_candidate",
        "up_manual.class_remap_override",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in SQL
    assert "CREATE OR REPLACE VIEW up_api.vector_output_geojson" in SQL
    assert "CREATE OR REPLACE VIEW up_api.review_queue" in SQL


def test_geometry_and_business_guards_present() -> None:
    assert "geometry(Polygon, 0) NOT NULL" in SQL
    assert "PDF_PAGE_POINTS_Y_DOWN_NO_CRS" in SQL
    assert "EPSG:5514" in SQL
    assert "vector_output_no_review_required_core" in SQL
    assert "up_type_def_zmen_navrh" in SQL
    assert "up_type_def_zmen_no_fill" in SQL

