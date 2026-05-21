# Infrastructure requirements v8

## Database

Use Postgres + PostGIS Docker.

Recommended image:

```yaml
image: postgis/postgis:18-3.6
```

Port policy:

```yaml
ports:
  - "5441:5432"
```

Never expose local Postgres on external `5432`.

Credentials:

```text
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=up_layer_extractor
```

## Frontend

Use:
- Vite
- React latest
- TypeScript
- Tailwind
- shadcn-style UI components
- design guidance from `C:\coding\shadcn_design_system`

## Backend

Use:
- FastAPI
- PyMuPDF
- Pydantic
- psycopg/SQLAlchemy or equivalent DB layer
- PostGIS geometry storage

## Future georeferencing

Path recorded:

```text
C:\coding\georef-ai-first-tool
```

Not implemented now.

Default georef adapter must be `noop`.

Do not output fake EPSG.
