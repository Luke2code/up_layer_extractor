# up_layer_extractor

Standalone UP layer extraction tool for orchestration workflows.

The repo implements the v11 instruction pack as a clean rebuild:

- FastAPI backend with PDF URL/upload intake, diagnostics-first routing, algorithm registry, manual review persistence, annotations, and config-driven remapping.
- Postgres/PostGIS migration model using only `up_import`, `up_stg`, `up_manual`, `up_core`, and `up_api`.
- Vite React/TypeScript/Tailwind operator UI with map preview, dependent filters, definition explorer, diagnostics/raw object tabs, remapping review, and selected-polygon edit/notes surfaces.

## Run

```bash
docker compose up -d db

python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt

npm install
npm --prefix frontend install
npm run dev
```

`npm run dev` starts the backend at `http://127.0.0.1:4101` and the frontend at `http://127.0.0.1:4100`.
The UI loads the bundled Květnice regression sample by default and proxies `/api/*` calls to `http://127.0.0.1:4101`.

To run only the frontend, use:

```bash
cd frontend
npm run dev
```

## Validate

```bash
. .venv/bin/activate
pytest backend/tests
python scripts/validate_migrations.py

cd frontend
npm run typecheck
npm test
npm run build
```

The migration is intentionally separate from the in-memory development API so the app can be exercised without a running PostGIS instance. Production persistence should apply `db/migrations/001_init_up_layer_extractor.sql` to the Docker database.
