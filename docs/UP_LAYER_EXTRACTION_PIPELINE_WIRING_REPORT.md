# UP Layer Extraction Pipeline Wiring Report

Date: 2026-05-19

## Gate 0 Inventory Before Editing

Backend endpoints:

- `GET /api/health`: service health.
- `GET /api/registry`: algorithm registry.
- `GET /api/sample/kvetnice`: static bundled GeoJSON sample.
- `POST /api/extract`: PDF URL extraction through `extract_url_to_feature_collection`.
- `POST /api/extract_upload`: PDF upload extraction through `extract_vector_candidates`.
- `POST /api/definitions/candidates`: in-memory definition grouping from a submitted FeatureCollection.
- `GET /api/definitions/candidates/sample`: definition grouping for the Kvetnice sample.
- `POST /api/definitions/approve`: in-memory vector/text definition approval.
- `POST /api/manual/edits`: stores manual correction records separately from raw geometry.
- `POST /api/manual/annotations`: stores labels/notes/warnings/decisions separately.
- `POST /api/remap/preview`: remap preview.
- `POST /api/remap/override`: in-memory remap override.
- `GET /api/state`: in-memory store state.
- `GET /api/diagnostics/babice-failure-demo`: diagnostic-only guard demo.

Current UI wiring:

- Intake bar loads static GeoJSON, arbitrary GeoJSON URL, PDF URL extraction, or PDF upload extraction.
- Map Preview renders the active FeatureCollection and uses active filters.
- Vector/Text Definitions currently call `/api/definitions/candidates` for non-large collections, otherwise local fallback.
- Legend Crops currently infer evidence from vector definition labels only; no real crop artifacts.
- Diagnostics currently shows selected metadata and diagnostics JSON.
- Raw Objects shows selected feature, raw object sample, and first features.
- Remapping is client-side from the active FeatureCollection properties and public remap config.
- Selected Polygon Review saves manual edits/annotations to backend APIs.

Sample-only/local-only behavior:

- Kvetnice loads from `frontend/public/kvetnice_up_layers_unified_pagecoords.geojson`.
- Definition Explorer has local fallback candidates when backend generation is skipped or unavailable.
- Remapping is generated in the browser, not persisted as a backend run artifact.
- Legend crop UI is a placeholder derived from labels, not image snapshots.

Current extraction data model:

- Backend returns a GeoJSON FeatureCollection with page metadata, diagnostics, raw object summaries, and `features`.
- Features are raw candidates with `UNCLASSIFIED/UNMAPPED` semantic fields unless provided by a fixture.
- Recent polygonization fix supports filled path commands (`l`, `c`, `qu`, `re`), curve flattening, holes, page-coordinate metadata, and no `MultiPolygon` output.

Current classification/remapping logic:

- `backend/app/remapping.py` maps existing `LAYER/CLASS/TYPE` fields with config-driven exact rules.
- Unknown classes remain `UNMAPPED` and require review.
- No evidence-driven bydlení/rekreace/smíšené obytné proposal pipeline exists yet.

Current diagnostics/logging implementation:

- Diagnostics include drawing/image/style counts and extraction stats.
- No structured `pipeline_traces`, `vector_traces`, `text_traces`, `classification_traces`, or `structured_errors` records exist yet.
- UI errors are mostly status strings and browser console checks in smoke tests.

Current vector extraction algorithm entry points:

- `diagnose_pdf(pdf_path)` selects/scans the best page and computes diagnostics.
- `choose_algorithm(diagnostics)` routes to vector fill, topology, raster pending, or diagnostic-only.
- `extract_vector_candidates(pdf_path, source_url)` builds candidate polygons.
- `extract_url_to_feature_collection(url)` downloads and extracts a PDF URL.

Current text extraction support:

- Diagnostics count rough token candidates from `page.get_text("text")`.
- No first-class text span/spec records are extracted or grouped.

Current legend crop/snapshot support:

- No image crop generation exists.
- Legend evidence is only exposed when a fixture already has `legend_symbol`.

Current frontend table/layout constraints:

- Tables are compact but simple; sticky header and horizontal scroll exist.
- No column visibility controls.
- Main map/review/results grid is fixed, with no persisted resizable/collapsible layout.
- Large collection safeguards disable duplicate validation overlay and skip backend definition roundtrip above 20k features.

Existing tests that must keep passing:

- Backend tests: algorithm registry, vector path polygonization, full-page-white diagnostic routing, API roundtrips, remapping, migration validation.
- Frontend tests: geometry helpers and remap helper tests.
- Build/typecheck and webapp smoke with Kvetnice sample.

Baseline validation before implementation:

- `PYTHONPATH=/mnt/c/coding/up_layer_extractor /mnt/c/coding/up_layer_extractor/.venv/bin/python -m pytest /mnt/c/coding/up_layer_extractor/backend/tests -q -s`: `21 passed`.
- `cd /mnt/c/coding/up_layer_extractor/frontend && npm run typecheck`: passed after restoring frontend dependencies with `npm install`.
- `cd /mnt/c/coding/up_layer_extractor/frontend && npm test -- --run`: `2 files`, `6 tests passed`.
- `cd /mnt/c/coding/up_layer_extractor/frontend && npm run build`: passed.

## Implementation Log

Implemented on 2026-05-19:

- Added backend enrichment for every PDF and GeoJSON collection:
  - `run_id`
  - `collection_id`
  - `source_filename`
  - `source_url`
  - `source_type`
  - `source_fingerprint`
  - `feature_count`
  - `vector_def_count`
  - `text_def_count`
  - `legend_crop_count`
  - `error_count`
  - `classification_status`
- Added explicit source detection:
  - `vector_pdf`
  - `mixed_pdf`
  - `raster_pdf`
  - `unsupported_pdf`
  - `geojson`
- Added first-class vector definition/spec records with:
  - path op counts (`l`, `c`, `qu`, `re`)
  - fill/stroke color and opacity
  - stroke width
  - dash raw/array/phase/normalized fields
  - source layer name
  - emitted feature counts
  - rejected reason
  - sample feature ids
- Added separate first-class text spec records with:
  - raw/normalized text
  - font/color/bbox fields
  - matched target code/label candidates
  - legend/classification candidate scores
  - rejected reasons
- Added structured pipeline trace records for:
  - source input/detection
  - metadata/inventory
  - vector path polygonization
  - dash extraction
  - text spec extraction
  - legend candidate detection
  - vector/text definition grouping
  - semantic classification
  - target scope filtering
  - export candidate generation
- Added vector extraction trace samples and text extraction trace samples.
- Added structured backend error records and geometry error candidate records.
- Added evidence-driven classification proposals for bydlení, rekreace, and smíšené obytné:
  - exact/code evidence
  - synonym/label evidence
  - source layer evidence
  - legend/text evidence
  - dash-sensitive confidence reduction
  - conflict detection
  - unknown evidence as `requires_review`
- Added legend snapshot bridge records:
  - real pixel crop generation remains unavailable;
  - UI now shows explicit `unavailable_reason` instead of pretending snapshots exist.
- Added export endpoint:
  - `POST /api/exports/pipeline_traces`
  - `POST /api/exports/vector_traces`
  - `POST /api/exports/text_traces`
  - `POST /api/exports/vector_definitions`
  - `POST /api/exports/text_definitions`
  - `POST /api/exports/classification_proposals`
  - `POST /api/exports/structured_errors`
- Updated `/api/extract` to load either PDF URLs or GeoJSON URLs.
- Updated `/api/extract_upload` to accept PDF or GeoJSON upload.
- Updated `/api/sample/kvetnice` to return backend-enriched sample records.
- Added PDF corpus validation command:

```bash
PYTHONPATH=/mnt/c/coding/up_layer_extractor \
/mnt/c/coding/up_layer_extractor/.venv/bin/python \
/mnt/c/coding/up_layer_extractor/scripts/validate_pdf_corpus.py
```

Corpus outputs:

- `/mnt/c/coding/up_layer_extractor/docs/pdf_validation_corpus.json`
- `/mnt/c/coding/up_layer_extractor/docs/pdf_validation_corpus.csv`

## Backend Endpoints Wired

- `GET /api/sample/kvetnice`: now backend-enriched.
- `POST /api/extract`: now accepts PDF URL or GeoJSON URL and returns enriched run records.
- `POST /api/extract_upload`: now accepts PDF or GeoJSON upload and returns enriched run records.
- `POST /api/exports/{kind}`: returns JSONL/CSV records for agent review.
- Existing manual edit, annotation, definition approval, remap preview, and state endpoints remain.

## Source Detection Behavior

PDF detection inspects drawing count, image count, and text span count. It classifies:

- vector-only PDFs as `vector_pdf`;
- vector plus image PDFs as `mixed_pdf`;
- image-only PDFs as `raster_pdf`;
- no vector/no image PDFs as `unsupported_pdf`.

GeoJSON upload/URL/sample sources are classified as `geojson`.

## Vector Spec Schema

Vector specs are grouped by fill/stroke style, opacity, stroke width, dash pattern, source layer, path command mix, and fill/stroke presence. Dash pattern is a first-class field:

- `dash_pattern_raw`
- `dash_array`
- `dash_phase`
- `dash_pattern_normalized`
- `has_dash_pattern`

The UI Vector Definitions table exposes these fields directly.

## Text Spec Schema

Text specs are separate from vector specs. They include text content, normalized content, font fields, color fields, bbox, code/label matches, candidate scores, and rejected reasons.

## Trace Schema

The pipeline emits:

- `pipeline_traces`
- `vector_extraction_traces`
- `text_extraction_traces`
- `classification_traces`

Primary decision variables are normal fields. `details` is only secondary context on pipeline steps.

## Error Schema

Structured errors include:

- run/source identity
- step
- algorithm
- severity
- error code
- message
- exception fields
- affected ids
- recovery action
- retryable flag

Geometry error candidates include rejected filled drawings with `polygonization_failed` review records.

## Classification Logic

Target scope:

- bydlení: `B`, `BI`, `BV`, `BH`, bydlení/obytné labels
- rekreace: `R`, `RI`, `RX`, rekreace labels
- smíšené obytné: `S`, `SO`, `SV`, `SC`, smíšené obytné/smíšené bydlení labels

Unknown evidence remains `UNMAPPED` and `requires_review`. Conflicting evidence becomes `conflicting_target_evidence`. Dash patterns reduce confidence and force review because dashed linework can indicate boundaries/reserves/limits rather than area fills.

## AI-Agent Improvement Logs / Exports

Export rows include run/source identifiers and avoid raw path arrays. Available formats:

- JSONL: pipeline traces, vector traces, text traces
- CSV: vector definitions, text definitions, classification proposals, structured errors

These logs are intended for comparing failures across the PDF corpus and safely improving rules without mutating raw geometry.

## UI Layout Behavior

- Intake now uses the backend for PDF URL, GeoJSON URL, PDF upload, GeoJSON upload, and sample loading.
- Tabs display active backend records where available:
  - Vector Definitions
  - Text Definitions
  - Legend Crops
  - Classification
  - Trace Logs
  - Errors
  - Diagnostics
  - Raw Objects
  - Remapping
- Tables are compact, sticky-header, horizontally scrollable, and support column visibility for trace-heavy views.
- Review panel width and results panel height are adjustable and persisted in `localStorage`.
- Review panel and results panel can be hidden/restored.
- Selected geometry highlight stroke is 3x thicker than before (`0.85` to `2.55`).

## Validation Results

Backend:

```bash
PYTHONPATH=/mnt/c/coding/up_layer_extractor \
/mnt/c/coding/up_layer_extractor/.venv/bin/python \
-m pytest /mnt/c/coding/up_layer_extractor/backend/tests -q -s
```

Result: `33 passed`.

Frontend:

```bash
cd /mnt/c/coding/up_layer_extractor/frontend
npm run typecheck
npm test -- --run
npm run build
```

Results:

- Typecheck: passed.
- Vitest: `2 files`, `6 tests passed`.
- Build: passed.

Migration:

```bash
/mnt/c/coding/up_layer_extractor/.venv/bin/python /mnt/c/coding/up_layer_extractor/scripts/validate_migrations.py
```

Result: `migration validation passed`.

PDF corpus:

```bash
PYTHONPATH=/mnt/c/coding/up_layer_extractor \
/mnt/c/coding/up_layer_extractor/.venv/bin/python \
/mnt/c/coding/up_layer_extractor/scripts/validate_pdf_corpus.py
```

Result: all 9 provided PDFs passed extraction:

| PDF | Features | Structured Errors |
| --- | ---: | ---: |
| UP__MNICHOVICE__538493__UZ_1__HLV.PDF | 2,236 | 0 |
| UP__SVETICE___A_PV__538841___UZ_1_HLV.pdf | 19,363 | 0 |
| UP_538728_RICANY_HLV.pdf | 49,967 | 0 |
| kamenice zcu.pdf | 10,920 | 0 |
| bykev_2-výkres základního členění.pdf | 1,712 | 0 |
| bykev_3-hlavní výkres.pdf | 4,832 | 0 |
| kamenice hlv.pdf | 56,642 | 0 |
| A_PV___MUKAROV___538523___UZ_2___HLV.pdf | 34,828 | 0 |
| A_PV___STRUHAROV___538825___UZ_2___ZCU.pdf | 4,925 | 0 |

UI smoke:

- Bundled sample smoke passed.
- Býkev upload smoke passed.
- Říčany large upload smoke passed.
- No browser console errors or page errors were raised.

Screenshots:

- `/mnt/c/coding/up_layer_extractor/docs/webapp-smoke.png`
- `/mnt/c/coding/up_layer_extractor/docs/webapp-bykev-upload.png`
- `/mnt/c/coding/up_layer_extractor/docs/webapp-ricany-upload.png`

## Known Limitations

- Legend pixel crop generation is explicitly marked unavailable. The bridge records text candidates and unavailable reasons, but does not yet render crop image artifacts.
- Vector/text proximity assignment is not spatially solved yet; nearby ids are present as fields but empty.
- Vector specs are style/path grouped records, not a persisted database table.
- Exports are generated from the active FeatureCollection submitted to the export endpoint, not from durable run storage.
- Geometry error candidates currently cover rejected filled drawings/polygonization failures. Full self-intersection and linework topology checks remain next-gate work.
- Resizing is implemented with persisted controls rather than drag handles.

## Next Gates

- Add actual legend crop image generation and artifact storage.
- Add spatial text-to-feature association.
- Add durable run storage for traces/exports.
- Add full geometry invalidity detection for self-intersections, open linework, slivers, unsupported commands, and invalid holes.
- Add operator review persistence for classification decisions.
- Add stronger municipality-specific style profiles only after legend/text evidence is available.
