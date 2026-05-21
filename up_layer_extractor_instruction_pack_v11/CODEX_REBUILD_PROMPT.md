# Codex rebuild prompt — up_layer_extractor v9

You are building a clean standalone repo:

```text
C:\coding\up_layer_extractor
```

This repo will be used as an external tool by the orchestration engine.

## Core instruction

Keep and expand the existing prototype behavior, but rebuild cleanly.

Do not copy bad prototype hacks into production architecture.

## Required DB schema model

Use only these schemas:

- `up_import`
- `up_stg`
- `up_manual`
- `up_core`
- `up_api`

Do not create:
- `up_source`
- `up_profile`
- `up_extract`
- `up_review`
- `up_validation`
- unprefixed generic schemas

## Required core tables

Implement migrations for:

### `up_core.up_def`
Plan/source definition. Must preserve:
- `up_id`
- municipality/source metadata
- PDF hash
- no fake CRS
- georef status

### `up_core.up_type_def`
Business type definition. Must preserve:
- `up_type_id`
- `layer`
- `class`
- `type`
- `layer_class`
- `class_type`
- `source_has_fill`
- `requires_text_id`
- `requires_boundary_topology`

Rules:
- `ZMEN.TYPE = NAVRH`
- `ZMEN.source_has_fill = false`
- `class_type = CLASS.1` for `STAV`
- `class_type = CLASS.2` for `NAVRH`

### `up_import.vector_import`
Raw PDF drawing extract.

This is the first stage of extracting polygons.

It must store all available style details:
- fill
- stroke/line
- dashing
- line width
- opacity
- hatch/pattern
- geom type
- bbox
- z-order
- path ops
- raw drawing JSON

Reject full-page white background polygon as fake success.

### `up_import.vector_def`
Vector style definition table.

Must include:
- legend crop/screenprint evidence
- style details
- mapping to `up_type_id`
- confidence/status

### `up_import.up_text_def`
Text layer definition table.

Must include:
- regex/parser rule
- font/style metadata if exposed
- label role
- association strategy
- mapping to `up_type_id`

### `up_stg.vector_stg_*`
Create staging tables:
- `vector_stg_candidates`
- `vector_stg_single_polygon`
- `vector_stg_text_assignment`
- `vector_stg_residual`

Every final candidate row must be a single `Polygon`, never `MultiPolygon`.

### `up_manual.vector_review`
Human decision/correction table.

### `up_core.vector_output`
Final approved vector output table.

Must include:
- `up_id`
- `up_type_id`
- `fid`
- `layer`
- `class`
- `type`
- `layer_class`
- `class_type`
- `text_id`
- `is_closed`
- geometry

### `up_api.*`
Read-only views for UI/orchestration.

## Algorithm registry

Implement algorithm registry. Each algorithm must declare:
- `algorithm_id`
- applicable diagnostics
- required PDF capabilities
- output contract
- confidence rules
- failure mode

Initial algorithms:

1. `vector_fill_style_polygon_v1`
   - For PDFs like Květnice where colored fills expose zoning polygons.

2. `vector_text_boundary_topology_v1`
   - For change areas / labels where fill is absent and dotted boundaries/text drive extraction.

3. `raster_style_segmentation_v1`
   - Fallback for PDFs where plan styles are raster/image based.

4. `diagnostic_only_v1`
   - Used when no safe extraction is possible.

## Routing diagnostics

Before choosing an algorithm, compute diagnostics:
- page count
- drawing count
- image count
- fill style counts
- stroke style counts
- background full-page count
- text label candidates
- raster/image coverage ratio
- legend candidate presence
- whether only full-page white polygon is found

If extraction returns only full-page white background, it is failure, not success.

## Květnice regression

Must preserve current Květnice behavior:
- RZVP layer
- ZMEN layer
- `CLASS`
- `TYPE`
- `LAYER_CLASS`
- `class_type`
- `text_id`
- `IS_CLOSED`
- single Polygon only
- no fake CRS

## Babice diagnostic

Babice currently returns only one `#ffffff` full-page polygon.

That must be treated as diagnostic failure:
- `classification_status = diagnostic_only`
- not as successful extraction

Codex must investigate:
- `page.get_drawings()`
- `page.get_images()`
- `page.get_text("dict")`
- `page.get_text("rawdict")`
- pixmap render
- fill/stroke/path/clip/transparency structure

If Babice is image/raster-based, route to `raster_style_segmentation_v1`, not Květnice fill algorithm.

## UI requirements

Use:
- Vite
- React latest
- TypeScript
- Tailwind
- shadcn-style components
- reuse design guidance from `C:\coding\shadcn_design_system`
- operator UI builder skill

Preserve current UI behavior:
- full plan preview
- plan overlay/contrast slider
- zoom around mouse point
- pan
- dependent segmented filters:
  - `LAYER`
  - `CLASS`
  - `TYPE`
  - `IS_CLOSED`
- polygon popup with:
  - `FID`
  - `LAYER_CLASS`
  - `TYPE`
  - `text_id`
- popup style:
  - subtle border
  - small radius
  - light grey bg
  - small grey key labels with colon
  - semi-bold values
  - hide null values
- selected polygon border:
  - yellow dotted
  - thin
- label toggles:
  - `text_id`
  - `FID`
  - `CLASS`
- Definition Explorer tabs:
  - Map Preview
  - Vector Definitions
  - Text Definitions
  - Diagnostics
  - Raw Objects

## Definition Explorer

Add interactive tables:

### Vector Definitions table
Must show:
- legend screenprint/crop
- source style key
- fill
- line/stroke
- dashing
- opacity
- hatch/pattern
- geom type
- z-order
- PDF evidence
- mapped `up_type_id`

### Text Definitions table
Must show:
- sample text
- regex/parser
- font
- size
- color
- bbox
- rotation
- association strategy
- mapped `up_type_id`

Do not invent styling details. Use `null` / `not_exposed` when PDF does not expose them.

## Infrastructure

Use Postgres/PostGIS Docker:
- image `postgis/postgis:18-3.6`
- external port `5441`
- never use external `5432`
- DB user/password `postgres/postgres`
- DB name `up_layer_extractor`

Future georeferencing:
- record adapter boundary for `C:\coding\georef-ai-first-tool`
- do not implement now
- default adapter is `noop`
- no fake EPSG

## Validation

Before reporting done:
- run backend tests
- run frontend build/test
- validate migrations
- validate no forbidden schemas
- validate Květnice regression
- validate Babice diagnostic failure
- validate single Polygon output
- validate full-page white background is rejected
- update docs and validation report


## v9 required additions

### Manual selected-polygon border editing

Implement selected polygon edit mode in the frontend and backend persistence:
- select polygon
- enter `Edit border`
- drag vertices
- add/delete vertices
- save/cancel edit
- persist to `up_manual.polygon_edit_session`
- do not overwrite raw import or staging geometry
- final `up_core.vector_output` must reference `manual_edit_id` if a manual correction was used

Validation after edit:
- geometry type is `Polygon`
- ring is closed
- geometry is valid
- area delta calculated
- review note required when area delta exceeds threshold

### Polygon labels and notes

Add UI and API support for polygon annotations:
- add label
- add note
- add warning
- mark decision/status

Persist to `up_manual.polygon_annotation`.

Do not overwrite extracted `text_id`.

### Auto-generate and select legend definitions

Implement candidate generation:
- detect observed vector styles from `up_import.vector_import`
- detect/crop legend evidence when possible
- create `up_stg.vector_def_candidate`
- create `up_stg.up_text_def_candidate`
- show candidates in Definition Explorer
- operator selects/approves definitions
- approved candidates become active `up_import.vector_def` and `up_import.up_text_def`

Do not invent style fields. Unknown fields are `NULL` / `not_exposed`.

### Definition Explorer UI

Add/keep tabs:
- Map Preview
- Vector Definitions
- Text Definitions
- Legend Crops
- Diagnostics
- Raw Objects

Vector Definitions table must show:
- select/active
- legend screenprint
- label text
- `LAYER`, `CLASS`, `TYPE`, `up_type_id`
- fill, stroke, width, opacity, dash, hatch/pattern, geom type, z-order
- sample count
- confidence/status

Text Definitions table must show:
- select/active
- role
- regex/parser
- sample text
- font/style data where exposed
- association strategy
- mapped `up_type_id`

### Algorithm improvement rule for every new PDF

For every new object/PDF:
1. run diagnostics
2. choose existing algorithm if diagnostics match
3. if existing algorithm fails and only minor tweaks are needed, improve it with tests
4. if diagnostics show a different PDF structure, add a new algorithm to the registry
5. classify the algorithm for future reuse
6. preserve Květnice regression
7. record the failure mode and routing variables

### Validation gates for v9

Codex must add tests for:
- manual edit persistence
- annotation persistence
- legend candidate generation
- vector definition selection
- text definition selection
- Květnice regression unchanged
- Babice full-page-white fake success rejected
- no `MultiPolygon` final output
- no fake CRS


## v10 mandatory addition — custom layer/class/type remapping

Incorporate `CUSTOM_LAYER_CLASS_TYPE_REMAPPING.md` and `config/vector_layer_class_type_remap.json`.

Implement remapping as a configurable subsystem:
- parse/load remap config into DB
- generate mapping candidates from vector definitions and text definitions
- let the operator review/override mappings
- write selected mapping into final `up_core.vector_output`

Do not hardcode the uploaded Python dicts directly into extraction logic. Convert them into persisted config and use services/tests around them.

Required tests:
- `CLASS_TYPE_CONFIG`: STAV/NAVRH/REZERVA evidence produces `class_type` suffix `.1/.2/.3`.
- `CLASS_MAP`: `RZVP.BI`, `RZVP.SV`, `ZMEN.Z`, `ZMEN.T`, and `CUST.X` resolve correctly.
- Unknown class stays `UNMAPPED` and `requires_manual_review=true`.
- Manual override wins over automatic mapping.
- Existing Květnice regression remains unchanged.


## Mandatory reference prototype inspection

Before implementing, inspect:
- `reference_prototype/v18_backend_url_intake/prototype/kvetnice_up_layers_preview_latest.html`
- `reference_prototype/v18_backend_url_intake/backend/up_layer_extractor_service.py`
- `reference_prototype/v17_ui_baseline/prototype/kvetnice_up_layers_preview_v17_labels_popup_intake.html`
- `reference_prototype/v17_ui_baseline/sample_data/kvetnice_up_layers_unified_pagecoords.geojson`

Preserve the working UI behavior and backend API shape, but rebuild cleanly with the schema, algorithm registry, remapping, diagnostics, and validation requirements in this pack.
