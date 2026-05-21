# DB migration spec — up_layer_extractor v9

## Required database

- Postgres + PostGIS
- Docker image: `postgis/postgis:18-3.6`
- External localhost port: `5441`
- Never expose Postgres externally on `5432`
- DB user: `postgres`
- DB password: `postgres`
- DB name: `up_layer_extractor`

## Required schemas

```sql
CREATE SCHEMA IF NOT EXISTS up_import;
CREATE SCHEMA IF NOT EXISTS up_stg;
CREATE SCHEMA IF NOT EXISTS up_manual;
CREATE SCHEMA IF NOT EXISTS up_core;
CREATE SCHEMA IF NOT EXISTS up_api;
```

Old schema names must not be created:
- `up_source`
- `up_profile`
- `up_extract`
- `up_review`
- `up_validation`
- unprefixed `source`, `profile`, `extract`, `review`, `validation`, `runtime`

## Core domain tables

### `up_core.up_def`

Represents one urban plan / plan drawing source.

Required columns:
- `up_id` primary key
- `obec_kod`
- `obec_name`
- `up_url`
- `source_url`
- `source_pdf_sha256`
- `source_pdf_name`
- `plan_name`
- `drawing_name`
- `valid_from`
- `pdf_page_count`
- `coordinate_system`
- `georef_status`
- `created_at`
- `updated_at`

Rules:
- `coordinate_system` is `PDF_PAGE_POINTS_Y_DOWN_NO_CRS` until real georeferencing exists.
- Do not fake EPSG:5514.
- Future georeferencing adapter must remain external / optional.

### `up_core.up_type_def`

Represents the business type/class definition.

Required columns:
- `up_type_id` primary key
- `layer` text, examples: `RZVP`, `ZMEN`
- `class` text, examples: `BI`, `RN`, `SV`, `SK`, `Z`, `P`
- `type` text, examples: `STAV`, `NAVRH`
- `layer_class` generated or maintained as `layer || '.' || class`
- `class_type` generated or maintained as `class || '.' || CASE type WHEN 'STAV' THEN '1' WHEN 'NAVRH' THEN '2' ELSE '0' END`
- `label_cz`
- `source_has_fill` boolean
- `requires_text_id` boolean
- `requires_boundary_topology` boolean
- `is_active` boolean

Rules:
- `ZMEN.TYPE = NAVRH`
- `ZMEN.source_has_fill = false`
- `RZVP.source_has_fill` may be true when PDF exposes fill styles.
- `class_type`: `CLASS.1 = STAV`, `CLASS.2 = NAVRH`.

## Import tables

### `up_import.pdf_source`

Stores downloaded/uploaded PDF source.

Required columns:
- `pdf_source_id`
- `up_id` nullable until source is linked to a plan
- `source_url`
- `file_name`
- `sha256`
- `byte_size`
- `created_at`
- `fetch_status`
- `fetch_error`
- `local_path` optional for local prototype only

### `up_import.pdf_page`

Stores page metadata and render references.

Required columns:
- `pdf_page_id`
- `pdf_source_id`
- `page_number`
- `width_pt`
- `height_pt`
- `rotation`
- `render_png_path`
- `render_dpi`
- `created_at`

### `up_import.vector_import`

First stage of polygon extraction: raw PDF drawings.

This is raw extraction, not business classification.

Required columns:
- `vector_import_id`
- `pdf_source_id`
- `pdf_page_id`
- `page_number`
- `drawing_index`
- `geom_type_raw`
- `geom_page` PostGIS geometry in page coordinates
- `is_closed`
- `bbox_page`
- `fill_rgb`
- `fill_hex`
- `fill_opacity`
- `stroke_rgb`
- `stroke_hex`
- `stroke_opacity`
- `stroke_width`
- `dash_array`
- `line_cap`
- `line_join`
- `hatch_or_pattern`
- `clip_path_id`
- `z_index`
- `path_ops_json`
- `raw_drawing_json`
- `is_background_candidate`
- `created_at`

Rules:
- Must preserve raw style details.
- Full-page white background must be flagged and excluded from success candidates.
- No classification here.

### `up_import.vector_def`

Defines vector styling definition from legend + observed PDF styles.

Required columns:
- `vector_def_id`
- `up_id`
- `pdf_source_id`
- `legend_crop_id`
- `source_style_key`
- `layer`
- `class`
- `type`
- `up_type_id` nullable until mapped
- `geom_type`
- `fill_hex`
- `fill_rgb`
- `fill_opacity`
- `stroke_hex`
- `stroke_rgb`
- `stroke_opacity`
- `stroke_width`
- `dash_array`
- `hatch_or_pattern`
- `line_cap`
- `line_join`
- `sample_bbox_page`
- `legend_label_text`
- `legend_label_confidence`
- `definition_status`
- `created_at`
- `updated_at`

Rules:
- If a style field is not exposed by the PDF, store `NULL`, not guessed values.
- Each definition must link to screenprint/crop evidence when possible.

### `up_import.up_text_def`

Defines text/label extraction rules.

Required columns:
- `up_text_def_id`
- `up_id`
- `pdf_source_id`
- `text_role`
- `regex_pattern`
- `layer`
- `class`
- `type`
- `up_type_id` nullable
- `font_name`
- `font_size_min`
- `font_size_max`
- `font_color_hex`
- `rotation`
- `bbox_rule`
- `association_strategy`
- `definition_status`
- `sample_text`
- `sample_bbox_page`
- `created_at`
- `updated_at`

Examples:
- `text_role = change_label`
- regex for `Z08`, `Z10`, `P2/01`, `P1/1`, `K05`
- association strategy: nearest polygon centroid, inside polygon, nearest dotted boundary region

## Staging tables

### `up_stg.vector_stg_candidates`

Algorithm-produced candidates after style filtering.

Required columns:
- `candidate_id`
- `up_id`
- `pdf_source_id`
- `pdf_page_id`
- `algorithm_id`
- `vector_def_id`
- `up_type_id`
- `geom_page`
- `is_closed`
- `source_vector_import_ids`
- `classification_status`
- `confidence`
- `diagnostics_json`
- `created_at`

### `up_stg.vector_stg_single_polygon`

Single polygon normalized output before review.

Required columns:
- `stg_polygon_id`
- `candidate_id`
- `up_id`
- `up_type_id`
- `fid_temp`
- `geom_page`
- `area_page`
- `bbox_page`
- `is_closed`
- `is_multipolygon_split`
- `split_group_id`
- `confidence`
- `created_at`

Rule:
- Every row must be a single `Polygon`, never `MultiPolygon`.

### `up_stg.vector_stg_text_assignment`

Text labels associated to candidate polygons.

Required columns:
- `text_assignment_id`
- `stg_polygon_id`
- `up_text_def_id`
- `text_id`
- `source_text`
- `text_bbox_page`
- `assignment_method`
- `assignment_distance`
- `confidence`
- `created_at`

### `up_stg.vector_stg_residual`

Validation residuals.

Required columns:
- `residual_id`
- `up_id`
- `up_type_id`
- `validation_mode`
- `residual_type`
- `geom_page`
- `area_page`
- `source_mask_ref`
- `generated_union_ref`
- `confidence`
- `requires_manual_review`
- `created_at`

Values:
- `residual_type = missing`
- `residual_type = extra`

## Manual review tables

### `up_manual.vector_review`

Human review decisions.

Required columns:
- `review_id`
- `stg_polygon_id`
- `up_id`
- `up_type_id`
- `decision`
- `corrected_geom_page`
- `corrected_text_id`
- `comment`
- `reviewed_by`
- `reviewed_at`

Allowed decisions:
- `approved`
- `rejected`
- `corrected`
- `needs_more_evidence`

## Core output tables

### `up_core.vector_output`

Final approved vector output.

Required columns:
- `vector_output_id`
- `up_id`
- `up_type_id`
- `fid`
- `layer`
- `class`
- `type`
- `layer_class`
- `class_type`
- `text_id`
- `geom_page`
- `is_closed`
- `source_pdf_sha256`
- `source_page_number`
- `source_algorithm_id`
- `source_confidence`
- `review_status`
- `created_at`
- `updated_at`

Rules:
- Every row must be a single `Polygon`.
- Must include both `up_id` and `up_type_id`.
- `layer/class/type` are denormalized from `up_core.up_type_def` for export convenience.
- No unreviewed `review_required` feature may be promoted to `up_core.vector_output` as trusted output.

## API views

### `up_api.vector_output_geojson`

Read view for UI/orchestration engine.

Required output properties:
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
- geometry in page coordinates unless georef adapter is applied

### `up_api.review_queue`

Read view for human review UI.

Should include:
- candidates
- residuals
- diagnostics
- legend evidence
- associated vector/text definitions


## v9 additions — manual editing, notes and legend candidates

### `up_import.legend_crop`

Stores legend screenprint/crop evidence used by definition generation.

Required columns:
- `legend_crop_id` primary key
- `up_id`
- `pdf_source_id`
- `pdf_page_id`
- `crop_bbox_page`
- `crop_image_path`
- `detected_by_algorithm_id`
- `confidence`
- `created_at`

Rule:
- Every approved `vector_def` should link to legend/crop evidence when the PDF exposes it.

### `up_stg.vector_def_candidate`

Generated candidate vector style definitions before approval.

Required columns:
- `vector_def_candidate_id` primary key
- `up_id`
- `pdf_source_id`
- `legend_crop_id`
- `source_style_key`
- vector style fields copied from observed styles
- `candidate_layer`
- `candidate_class`
- `candidate_type`
- `candidate_up_type_id`
- `legend_label_text`
- `legend_label_confidence`
- `sample_count`
- `sample_bbox_page`
- `candidate_status`
- `created_at`
- `updated_at`

Rules:
- Candidate status values: `candidate`, `selected`, `rejected`, `approved`, `deprecated`.
- Do not hardcode Květnice colors as universal definitions.

### `up_stg.up_text_def_candidate`

Generated candidate text/label definitions before approval.

Required columns:
- `up_text_def_candidate_id` primary key
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
- `updated_at`

### `up_manual.polygon_edit_session`

Stores manual border corrections for selected polygons.

Required columns:
- `manual_edit_id` primary key
- `up_id`
- `stg_polygon_id`
- `fid` nullable until final output
- `edit_status`
- `edit_reason`
- `geom_page_before` geometry Polygon
- `geom_page_after` geometry Polygon
- `area_before_page_units`
- `area_after_page_units`
- `area_delta_pct`
- `is_closed_after`
- `is_valid_after`
- `created_by`
- `created_at`
- `updated_at`

Rules:
- Manual border edits do not overwrite raw or staging geometry.
- `up_core.vector_output` references the approved `manual_edit_id` when a manual correction was used.

### `up_manual.polygon_vertex_edit`

Optional detailed audit trail for vertex-level edits.

Required columns:
- `vertex_edit_id` primary key
- `manual_edit_id`
- `operation`
- `vertex_index`
- `point_before`
- `point_after`
- `created_at`

### `up_manual.polygon_annotation`

Stores labels, notes, warnings and review decisions attached to polygons.

Required columns:
- `annotation_id` primary key
- `up_id`
- `stg_polygon_id` nullable
- `vector_output_id` nullable
- `annotation_type`
- `label_text`
- `note_text`
- `created_by`
- `created_at`
- `updated_at`
- `is_active`

Rules:
- `text_id` is extracted from the PDF and must not be overwritten by manual notes.
- Manual label override is stored separately from `text_id`.

### `up_core.vector_output` v9 provenance additions

Add/require:
- `source_stg_polygon_id`
- `manual_edit_id` nullable
- `label_override` nullable
- `review_status`
- `reviewed_by`
- `reviewed_at`
- `confidence_final`

Rule:
- Final output must be traceable back to raw import, staging candidate and manual correction where applicable.


## v10 additions — custom layer/class/type remapping

Add configuration-driven remapping tables. The extractor must separate raw extraction from semantic normalization.

### up_import.class_remap_config
Stores imported class mapping config versions, including `CLASS_TYPE_CONFIG`, `CLASS_GROUP_MAP`, and `CLASS_MAP` from the legacy `RZV_CUSTOM_MAP` source.

Minimum columns:
```sql
config_id bigserial primary key,
config_name text not null,
version text not null,
source_ref text,
class_type_config jsonb not null,
class_group_map jsonb not null,
class_map jsonb not null,
is_active boolean not null default false,
created_at timestamptz not null default now()
```

### up_stg.class_remap_candidate
Stores automatic proposals from vector/text/legend evidence to canonical `LAYER`, `CLASS`, `TYPE`, `LAYER_CLASS`, and `class_type`.

### up_manual.class_remap_override
Stores human-approved overrides. Manual overrides must never mutate `up_import.vector_import` or raw style/text definitions.

### up_core.up_type_def extension
`up_core.up_type_def` must include or link to:
- `layer`
- `class`
- `type_code`
- `class_type`
- `layer_class`
- `group_label`
- `display_label`
- `source_config_id`
- `is_custom`
- `ref`

Hard rule: semantic remapping is data-driven and reviewable. Unknown or ambiguous mappings become review tasks, not silent guesses.
