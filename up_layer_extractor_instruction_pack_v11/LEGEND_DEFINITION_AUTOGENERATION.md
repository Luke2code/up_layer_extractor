# Legend definition auto-generation and selection

## Purpose

Automatically generate candidate `vector_def` and `up_text_def` definitions from the PDF, then let the operator select/approve them.

## Why this matters

New PDFs will not always use Květnice styles. The tool must not hardcode one municipality's colors.

## Required backend flow

1. Extract raw drawings to `up_import.vector_import`.
2. Compute style clusters:
   - fill color
   - stroke color
   - stroke width
   - dash array
   - opacity
   - hatch/pattern marker
   - geom type
   - z-order range
3. Detect legend area candidates:
   - page side bands
   - text density
   - repeated symbol + label patterns
   - observed style samples near labels
4. Create `up_import.legend_crop` records.
5. Create `up_stg.vector_def_candidate` records.
6. Create `up_stg.up_text_def_candidate` records.
7. UI shows candidate definitions in Definition Explorer.
8. Operator selects/approves definitions.
9. Approved definitions become active `up_import.vector_def` and `up_import.up_text_def` rows.
10. Extraction can then produce classified staging polygons.

## `up_import.legend_crop`

Required columns:
- `legend_crop_id`
- `up_id`
- `pdf_source_id`
- `pdf_page_id`
- `crop_bbox_page`
- `crop_image_path`
- `detected_by_algorithm_id`
- `confidence`
- `created_at`

## `up_stg.vector_def_candidate`

Required columns:
- `vector_def_candidate_id`
- `up_id`
- `pdf_source_id`
- `legend_crop_id`
- `source_style_key`
- all exposed vector style fields
- `candidate_layer`
- `candidate_class`
- `candidate_type`
- `candidate_up_type_id`
- `legend_label_text`
- `legend_label_confidence`
- `sample_count`
- `sample_bbox_page`
- `candidate_status`: `candidate`, `selected`, `rejected`, `approved`
- `created_at`

## `up_stg.up_text_def_candidate`

Required columns:
- `up_text_def_candidate_id`
- `up_id`
- `pdf_source_id`
- `text_role`
- `regex_pattern`
- `sample_text`
- `sample_count`
- `font_name`
- `font_size_min`
- `font_size_max`
- `font_color_hex`
- `rotation`
- `candidate_layer`
- `candidate_class`
- `candidate_type`
- `candidate_status`
- `created_at`

## UI requirements

Definition Explorer tabs:
- Vector Definitions
- Text Definitions
- Legend Crops

Vector Definitions table columns:
- select/active
- status
- legend screenprint
- label text
- `LAYER`
- `CLASS`
- `TYPE`
- `up_type_id`
- fill
- stroke
- width
- dash
- hatch/pattern
- opacity
- geom type
- sample count
- confidence

Text Definitions table columns:
- select/active
- role
- regex
- sample text
- `LAYER`
- `CLASS`
- `TYPE`
- font
- size
- color
- rotation
- association strategy
- confidence

## Guardrails

- Do not invent style fields.
- Unknown style field = `NULL` / `not_exposed`.
- Do not promote candidate to approved without evidence.
- Keep multiple candidates if ambiguous.
- Operator selection must be persisted.
