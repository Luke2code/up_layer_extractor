from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = REPO_ROOT / "db" / "migrations" / "001_init_up_layer_extractor.sql"

REQUIRED_SCHEMAS = {"up_import", "up_stg", "up_manual", "up_core", "up_api"}
FORBIDDEN_SCHEMAS = {
    "up_source",
    "up_profile",
    "up_extract",
    "up_review",
    "up_validation",
    "source",
    "profile",
    "extract",
    "review",
    "validation",
    "runtime",
}
REQUIRED_TABLES = {
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
}


def main() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8")
    created_schemas = set(re.findall(r"CREATE\s+SCHEMA\s+IF\s+NOT\s+EXISTS\s+([a-z_]+)", sql, re.I))
    missing_schemas = REQUIRED_SCHEMAS - created_schemas
    if missing_schemas:
        raise SystemExit(f"missing schemas: {sorted(missing_schemas)}")

    forbidden = created_schemas & FORBIDDEN_SCHEMAS
    if forbidden:
        raise SystemExit(f"forbidden schemas created: {sorted(forbidden)}")

    missing_tables = [name for name in REQUIRED_TABLES if f"CREATE TABLE IF NOT EXISTS {name}" not in sql]
    if missing_tables:
        raise SystemExit(f"missing tables: {missing_tables}")

    required_snippets = [
        "geometry(Polygon, 0) NOT NULL",
        "PDF_PAGE_POINTS_Y_DOWN_NO_CRS",
        "vector_output_no_review_required_core",
        "up_api.vector_output_geojson",
        "up_api.review_queue",
        "class_remap_config_single_active",
    ]
    for snippet in required_snippets:
        if snippet not in sql:
            raise SystemExit(f"missing migration guard: {snippet}")

    print("migration validation passed")


if __name__ == "__main__":
    main()

