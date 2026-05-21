# AGENTS.md — up_layer_extractor

## Mission

Build a standalone external UP layer extraction tool for the orchestration engine.

The tool extracts vector/text/style definitions and polygon outputs from urban planning PDFs.

## Working principles

- Preserve business logic.
- Revalidate from scratch before major changes.
- Do not fake GIS truth.
- Do not fake EPSG/S-JTSK.
- Do not treat full-page white background as successful extraction.
- Every final polygon must be single `Polygon`, not `MultiPolygon`.
- Every output feature must keep `up_id` and `up_type_id`.
- Improve algorithm registry with every new PDF object.
- Reuse algorithms where possible.
- Add new algorithms when the diagnostic variables prove that an existing algorithm is the wrong fit.

## Required repo stack

Backend:
- Python
- FastAPI
- PyMuPDF
- Postgres/PostGIS

Frontend:
- Vite
- React latest
- TypeScript
- Tailwind
- shadcn-style components
- use design system guidance from `C:\coding\shadcn_design_system`

DB:
- Postgres/PostGIS Docker
- image `postgis/postgis:18-3.6`
- external localhost port `5441`
- never external `5432`
- user/password `postgres/postgres`

## Required schemas

Use:
- `up_import`
- `up_stg`
- `up_manual`
- `up_core`
- `up_api`

Do not use:
- `up_source`
- `up_profile`
- `up_extract`
- `up_review`
- `up_validation`
- generic unprefixed schemas

## Required business tables

- `up_core.up_def`
- `up_core.up_type_def`
- `up_import.vector_import`
- `up_import.vector_def`
- `up_import.up_text_def`
- `up_stg.vector_stg_candidates`
- `up_stg.vector_stg_single_polygon`
- `up_stg.vector_stg_text_assignment`
- `up_stg.vector_stg_residual`
- `up_manual.vector_review`
- `up_core.vector_output`
- `up_api` read views

## Business field contract

Every output feature must support:
- `FID`
- `up_id`
- `up_type_id`
- `LAYER`
- `CLASS`
- `TYPE`
- `LAYER_CLASS`
- `class_type`
- `text_id`
- `IS_CLOSED`

Rules:
- `ZMEN.TYPE = NAVRH`
- `ZMEN.source_has_fill = false`
- `class_type = CLASS.1` for `STAV`
- `class_type = CLASS.2` for `NAVRH`

## Extraction stages

1. `vector_import`
   - raw PDF drawings
   - all styles and path details
   - no classification

2. `vector_def`
   - style definition from legend and observed drawing styles
   - map to `up_type_id`

3. `up_text_def`
   - label/text definition
   - regex/parser
   - association rule

4. `vector_stg_*`
   - algorithm candidates
   - split to single polygons
   - assign text
   - compute residuals

5. `up_manual`
   - human review/corrections

6. `up_core.vector_output`
   - approved final output

## Algorithm registry

Every algorithm must define:
- ID
- diagnostics preconditions
- input contract
- output contract
- confidence rules
- failure mode
- tests

Initial algorithms:
- `vector_fill_style_polygon_v1`
- `vector_text_boundary_topology_v1`
- `raster_style_segmentation_v1`
- `diagnostic_only_v1`

## Required UI

- Map preview
- Vector Definitions table
- Text Definitions table
- Diagnostics tab
- Raw Objects tab
- dependent segmented filters
- plan overlay slider
- popup
- selected dotted border
- label toggles
- file/URL intake

## Validation gates

Do not mark done until:
- migrations pass
- tests pass
- Květnice regression passes
- Babice failure mode is handled correctly
- full-page white background is rejected
- no forbidden schemas exist
- docs and validation report updated


## v9 additional instructions

### Manual polygon editing

The selected polygon border can be edited manually, but only through `up_manual` correction tables. Do not overwrite raw imports or staging candidates.

Required persistence:
- `up_manual.polygon_edit_session`
- optional `up_manual.polygon_vertex_edit`
- final `up_core.vector_output.manual_edit_id`

### Polygon labels and notes

Support labels, notes, warnings and review decisions through `up_manual.polygon_annotation`.

`text_id` is extracted source text and must not be overwritten by manual labels.

### Legend definition auto-generation

Every PDF must attempt diagnostics and candidate definition generation:
- `up_import.legend_crop`
- `up_stg.vector_def_candidate`
- `up_stg.up_text_def_candidate`

Definitions become active only after selection/approval.

### Do not fake certainty

If the system cannot determine a style or boundary, mark it `review_required` or route to `diagnostic_only_v1`.

### Current mandatory UI behavior

Keep the current UI as close as possible:
- full plan preview
- dependent segmented filters
- plan overlay slider
- exact-filter raster validation with clear source labeling
- popup with basic attrs
- selected dotted border
- label toggles
- file/URL intake
- Definition Explorer tables
- manual polygon edit mode
- polygon label/note panel


## v10 remapping guardrails

- Treat layer/class/type remapping as data/config, not as scattered code branches.
- Preserve raw extracted evidence before applying semantic remapping.
- Manual overrides must be auditable and must not overwrite raw imports or staging candidates.
- Unknown classes must not be guessed. Use `UNMAPPED` and require review.
- `CUST.*` requires `REF` / manual display label.
- Every change to remapping requires tests for Květnice regression and at least one unmapped/ambiguous case.
