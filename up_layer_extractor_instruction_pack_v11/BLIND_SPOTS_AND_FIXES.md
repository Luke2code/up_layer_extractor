# Blind spots and fixes — v9 revalidation

## Result

`passed_with_required_updates`

The v8 architecture was directionally correct, but it missed several operational realities. These are now required in v9.

## Blind spot 1 — manual polygon border editing was not modeled

Problem:
- The UI allowed review, but the database model did not clearly store a human-adjusted polygon border.
- Without this, corrected geometries would either overwrite algorithm output or get lost as UI-only state.

Fix:
- Add `up_manual.polygon_edit_session`.
- Add `up_manual.polygon_vertex_edit` for audit detail when needed.
- Add `manual_edit_id`, `review_status`, `reviewed_by`, `reviewed_at` provenance to final output.
- Never overwrite `up_import.vector_import` or `up_stg.vector_stg_*` rows.

Rule:
```text
raw extraction stays raw
algorithm candidate stays reproducible
manual correction is a separate correction layer
core output references the approved correction
```

## Blind spot 2 — polygon labels and notes were missing as first-class data

Problem:
- `text_id` is not enough.
- Operators need labels, comments, warnings, issue notes, and review decisions attached to individual polygons.

Fix:
- Add `up_manual.polygon_annotation`.
- Add output fields/views for `label_override`, `display_label`, `note_count`, `has_review_note`.
- Notes must be user-authored and timestamped, not baked into raw extraction.

## Blind spot 3 — legend definition auto-generation was underspecified

Problem:
- `vector_def` existed, but there was no clear workflow for generating candidate definitions from observed styles and legend crops.
- Risk: Codex hardcodes Květnice colors or manually creates definitions without evidence.

Fix:
- Add `up_import.legend_crop`.
- Add `up_stg.vector_def_candidate`.
- Add `up_stg.up_text_def_candidate`.
- UI must provide an interactive Definition Explorer where the operator selects/approves mappings.

Rule:
```text
observed style → candidate definition → human/agent selection → active vector_def/up_text_def → extraction
```

## Blind spot 4 — selected legend definition was not explicit

Problem:
- Multiple candidate definitions can map to similar styles.
- The system needs to know which definition was used.

Fix:
- Add `selected_vector_def_id` and `selected_text_def_id` to staging candidates where applicable.
- Add `definition_status`: `candidate`, `selected`, `rejected`, `approved`, `deprecated`.

## Blind spot 5 — exact-filter raster validation can look authoritative even when source mask is weak

Problem:
- Raster validation can lie if it is generated from output polygons instead of independent source evidence.

Fix:
- Validation overlays must declare `validation_source`: `source_raster_mask`, `source_vector_style`, `generated_output_footprint`, or `unavailable`.
- If validation is generated from output polygons only, label it as footprint preview, not source validation.
- For `ZMEN`, fill-raster validation is not valid because `ZMEN` has no fill color.

## Blind spot 6 — genericity claim was too broad

Problem:
- The tool is not generic for any arbitrary PDF.

Correct statement:
- Generic for PDFs where the algorithm registry can diagnose available evidence and choose a matching algorithm.
- Not automatically generic for raster-only or non-standard encoded PDFs unless `raster_style_segmentation_v1` or another algorithm supports them.

## Required validation gates

Before marking done:
- Květnice regression still passes.
- Babice failure mode does not return fake success.
- Manual polygon edit roundtrip works.
- Polygon annotation roundtrip works.
- Legend definition candidate generation works.
- Operator can select/approve a `vector_def`.
- Final output has provenance to raw/staging/manual rows.
- No `MultiPolygon` in final output.
- No fake CRS.
