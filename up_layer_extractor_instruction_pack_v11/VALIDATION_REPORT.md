# Validation Report — v11

## Status
passed

## Revalidation from scratch

The v10 pack was inspected and found to contain specs/config/docs but not the working prototype reference files. v11 fixes that.

## Prototype inclusion validation

Passed:
- `reference_prototype/v18_backend_url_intake/backend/up_layer_extractor_service.py` exists.
- `reference_prototype/v18_backend_url_intake/prototype/kvetnice_up_layers_preview_latest.html` exists.
- `reference_prototype/v18_backend_url_intake/profiles/babice_z12_profile.yaml` exists.
- `reference_prototype/v17_ui_baseline/prototype/kvetnice_up_layers_preview_v17_labels_popup_intake.html` exists.
- `reference_prototype/v17_ui_baseline/sample_data/kvetnice_up_layers_unified_pagecoords.geojson` exists.
- `REFERENCE_PROTOTYPE_MANIFEST.md` exists.
- deprecated old repo naming was checked and removed from implementation/spec text.
- remapping config remains included: `config/vector_layer_class_type_remap.json`.
- `AGENTS.md` remains included.

## Guardrail

The included prototype is a reference implementation, not production architecture. Codex must preserve behavior and styling, but rebuild cleanly according to the current SSOT, DB schema, algorithm registry, remapping system, diagnostics, and validation requirements.
