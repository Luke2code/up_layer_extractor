# Validation report

Status: passed.

## Covered gates

- Required schemas are represented in the migration: `up_import`, `up_stg`, `up_manual`, `up_core`, `up_api`.
- Forbidden schemas are not created by the migration validator.
- Final output and staging polygon tables use `geometry(Polygon, 0)` and include single-polygon guards.
- `EPSG:5514` is explicitly rejected by a no-fake-CRS constraint.
- Algorithm registry includes the four required algorithms.
- Full-page white background routes to `diagnostic_only_v1` and emits no trusted features.
- Květnice regression fixture preserves `RZVP`, `ZMEN`, `CLASS`, `TYPE`, `LAYER_CLASS`, `class_type`, `text_id`, `IS_CLOSED`, and single `Polygon` geometries.
- Manual edit and polygon annotation APIs persist separate correction/annotation records and do not overwrite raw imports.
- Legend/vector/text definition candidates can be generated and approved.
- Remapping loads the v10 config and keeps unknown classes as `UNMAPPED` with review required.

## Commands run

```bash
. .venv/bin/activate && pytest -s backend/tests
# 16 passed

. .venv/bin/activate && python scripts/validate_migrations.py
# migration validation passed

docker compose up -d db
docker exec -i up_layer_extractor_postgis psql -U postgres -d up_layer_extractor -v ON_ERROR_STOP=1 < db/migrations/001_init_up_layer_extractor.sql
# migration applied successfully; second run also succeeds

cd frontend && npm run typecheck
# passed

cd frontend && npm test
# 2 files, 6 tests passed

cd frontend && npm run build
# built successfully

cd frontend && npm audit --audit-level=moderate
# found 0 vulnerabilities

python3 /mnt/c/Users/Me/.codex/skills/webapp-testing/scripts/with_server.py \
  --server "bash -lc '. .venv/bin/activate && uvicorn backend.app.main:app --host 127.0.0.1 --port 4101'" --port 4101 \
  --server "bash -lc 'cd frontend && npm run dev -- --host 127.0.0.1 --port 4100 --strictPort'" --port 4100 \
  --timeout 60 -- .venv/bin/python scripts/smoke_webapp.py
# webapp smoke passed; screenshot=docs/webapp-smoke.png
```

## Artifacts

- Browser smoke screenshot: `docs/webapp-smoke.png`
- Migration: `db/migrations/001_init_up_layer_extractor.sql`
- Regression fixture: `frontend/public/kvetnice_up_layers_unified_pagecoords.geojson`
