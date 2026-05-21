# up_layer_extractor architecture

## Runtime boundary

The service is an external tool for the orchestration engine. It does not invent georeferencing and keeps the coordinate system as `PDF_PAGE_POINTS_Y_DOWN_NO_CRS` until an external georef adapter is connected.

## Data flow

```text
PDF URL/upload
-> diagnostics
-> algorithm registry route
-> up_import raw evidence
-> up_stg candidates/definition proposals/remap proposals
-> up_manual corrections/annotations/overrides
-> up_core approved output
-> up_api read views
```

The development FastAPI app uses in-memory persistence for operator actions so the UI can be exercised without a running database. The production persistence contract is captured in `db/migrations/001_init_up_layer_extractor.sql`.

## Algorithm routing

The registry exposes:

- `vector_fill_style_polygon_v1`
- `vector_text_boundary_topology_v1`
- `raster_style_segmentation_v1`
- `diagnostic_only_v1`

Routing rejects the known fake-success case where the only vector polygon is a full-page white background. That result is emitted as `classification_status=diagnostic_only` with no trusted features.

## Remapping

Layer/class/type normalization is data-driven from `config/vector_layer_class_type_remap.json`.

Precedence:

1. Manual override.
2. Active config exact class map.
3. Prefix group map.
4. Type evidence config.
5. `UNMAPPED` with `requires_manual_review=true`.

Unknown classes are not guessed. `CUST.*` requires a reference/manual label.

## UI

The frontend is a dense operator workbench:

- full plan preview with plan overlay slider
- mouse-centered zoom and pan
- dependent `LAYER`, `CLASS`, `TYPE`, `IS_CLOSED` filters
- selected polygon popup with the required business fields
- label toggles for `text_id`, `FID`, and `CLASS`
- Definition Explorer tabs for map, vector definitions, text definitions, legend crops, diagnostics, raw objects, and remapping
- manual polygon border editing and annotations

