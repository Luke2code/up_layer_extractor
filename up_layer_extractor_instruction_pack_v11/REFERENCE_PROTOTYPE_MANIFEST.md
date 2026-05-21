# Reference Prototype Manifest — v11

This instruction pack now includes working prototype reference files.

## Included reference prototypes

### `reference_prototype/v18_backend_url_intake/`
Purpose: backend URL/upload intake reference and latest backend service prototype.

Included:
- `backend/up_layer_extractor_service.py`
- `backend/requirements.txt`
- `profiles/babice_z12_profile.yaml`
- `prototype/kvetnice_up_layers_preview_latest.html`
- `prototype/kvetnice_up_layers_preview_v18_babice_url_backend.html`
- V18 docs and validation report

Use this to replicate:
- FastAPI backend shape
- `/api/health`
- `/api/extract`
- `/api/extract_upload`
- PDF URL normalization
- upload flow
- Babice failure-mode diagnostics

Do not copy this backend blindly into production. Rebuild cleanly with the algorithm registry and DB schema defined in this pack.

### `reference_prototype/v17_ui_baseline/`
Purpose: UI behavior and styling reference.

Included:
- `prototype/kvetnice_up_layers_preview_v17_labels_popup_intake.html`
- `prototype/kvetnice_up_layers_preview_latest.html`
- `sample_data/kvetnice_up_layers_unified_pagecoords.geojson`
- V17 docs and validation report

Use this to replicate:
- full-plan preview behavior
- layer/class/type filters
- dependent filtering
- labels
- popup behavior
- selected polygon border
- file/URL intake UX
- `class_type` field display

## Rebuild rule

Codex must inspect these files before implementing the new repo, but the target repo must be rebuilt cleanly:

- preserve current functionality and visual behavior unless explicitly improved;
- do not hardcode Květnice-only logic into generic runtime;
- keep algorithm registry, diagnostics-first routing, DB persistence, and review workflow from the instruction docs;
- keep all business fields and remapping logic.
