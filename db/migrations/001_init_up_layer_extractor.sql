CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS up_import;
CREATE SCHEMA IF NOT EXISTS up_stg;
CREATE SCHEMA IF NOT EXISTS up_manual;
CREATE SCHEMA IF NOT EXISTS up_core;
CREATE SCHEMA IF NOT EXISTS up_api;

CREATE TABLE IF NOT EXISTS up_core.up_def (
  up_id text PRIMARY KEY,
  obec_kod text,
  obec_name text,
  up_url text,
  source_url text,
  source_pdf_sha256 text,
  source_pdf_name text,
  plan_name text,
  drawing_name text,
  valid_from date,
  pdf_page_count integer,
  coordinate_system text NOT NULL DEFAULT 'PDF_PAGE_POINTS_Y_DOWN_NO_CRS',
  georef_status text NOT NULL DEFAULT 'noop',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT up_def_no_fake_crs CHECK (coordinate_system <> 'EPSG:5514')
);

CREATE TABLE IF NOT EXISTS up_import.class_remap_config (
  config_id bigserial PRIMARY KEY,
  config_name text NOT NULL,
  version text NOT NULL,
  source_ref text,
  class_type_config jsonb NOT NULL,
  class_group_map jsonb NOT NULL,
  class_map jsonb NOT NULL,
  is_active boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS class_remap_config_single_active
ON up_import.class_remap_config (is_active)
WHERE is_active;

CREATE TABLE IF NOT EXISTS up_core.up_type_def (
  up_type_id text PRIMARY KEY,
  layer text NOT NULL,
  "class" text NOT NULL,
  "type" text NOT NULL,
  type_code text GENERATED ALWAYS AS (
    CASE "type"
      WHEN 'STAV' THEN '1'
      WHEN 'NAVRH' THEN '2'
      WHEN 'REZERVA' THEN '3'
      ELSE '0'
    END
  ) STORED,
  layer_class text GENERATED ALWAYS AS (layer || '.' || "class") STORED,
  class_type text GENERATED ALWAYS AS (
    "class" || '.' ||
    CASE "type"
      WHEN 'STAV' THEN '1'
      WHEN 'NAVRH' THEN '2'
      WHEN 'REZERVA' THEN '3'
      ELSE '0'
    END
  ) STORED,
  label_cz text,
  group_label text,
  display_label text,
  source_has_fill boolean NOT NULL DEFAULT false,
  requires_text_id boolean NOT NULL DEFAULT false,
  requires_boundary_topology boolean NOT NULL DEFAULT false,
  source_config_id bigint REFERENCES up_import.class_remap_config(config_id),
  is_custom boolean NOT NULL DEFAULT false,
  ref text,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT up_type_def_zmen_navrh CHECK (layer <> 'ZMEN' OR "type" = 'NAVRH'),
  CONSTRAINT up_type_def_zmen_no_fill CHECK (layer <> 'ZMEN' OR source_has_fill = false),
  CONSTRAINT up_type_def_custom_ref CHECK (is_custom = false OR ref IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS up_import.pdf_source (
  pdf_source_id bigserial PRIMARY KEY,
  up_id text REFERENCES up_core.up_def(up_id),
  source_url text,
  file_name text,
  sha256 text,
  byte_size bigint,
  created_at timestamptz NOT NULL DEFAULT now(),
  fetch_status text NOT NULL DEFAULT 'pending',
  fetch_error text,
  local_path text
);

CREATE TABLE IF NOT EXISTS up_import.pdf_page (
  pdf_page_id bigserial PRIMARY KEY,
  pdf_source_id bigint NOT NULL REFERENCES up_import.pdf_source(pdf_source_id) ON DELETE CASCADE,
  page_number integer NOT NULL,
  width_pt numeric NOT NULL,
  height_pt numeric NOT NULL,
  rotation integer NOT NULL DEFAULT 0,
  render_png_path text,
  render_dpi integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (pdf_source_id, page_number)
);

CREATE TABLE IF NOT EXISTS up_import.vector_import (
  vector_import_id bigserial PRIMARY KEY,
  pdf_source_id bigint NOT NULL REFERENCES up_import.pdf_source(pdf_source_id) ON DELETE CASCADE,
  pdf_page_id bigint NOT NULL REFERENCES up_import.pdf_page(pdf_page_id) ON DELETE CASCADE,
  page_number integer NOT NULL,
  drawing_index integer NOT NULL,
  geom_type_raw text,
  geom_page geometry(Geometry, 0),
  is_closed boolean,
  bbox_page jsonb,
  fill_rgb jsonb,
  fill_hex text,
  fill_opacity numeric,
  stroke_rgb jsonb,
  stroke_hex text,
  stroke_opacity numeric,
  stroke_width numeric,
  dash_array jsonb,
  line_cap text,
  line_join text,
  hatch_or_pattern text,
  clip_path_id text,
  z_index integer,
  path_ops_json jsonb,
  raw_drawing_json jsonb,
  is_background_candidate boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS up_import.legend_crop (
  legend_crop_id bigserial PRIMARY KEY,
  up_id text NOT NULL REFERENCES up_core.up_def(up_id),
  pdf_source_id bigint NOT NULL REFERENCES up_import.pdf_source(pdf_source_id) ON DELETE CASCADE,
  pdf_page_id bigint REFERENCES up_import.pdf_page(pdf_page_id),
  crop_bbox_page jsonb,
  crop_image_path text,
  detected_by_algorithm_id text,
  confidence numeric,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS up_import.vector_def (
  vector_def_id bigserial PRIMARY KEY,
  up_id text NOT NULL REFERENCES up_core.up_def(up_id),
  pdf_source_id bigint REFERENCES up_import.pdf_source(pdf_source_id),
  legend_crop_id bigint REFERENCES up_import.legend_crop(legend_crop_id),
  source_style_key text NOT NULL,
  layer text,
  "class" text,
  "type" text,
  up_type_id text REFERENCES up_core.up_type_def(up_type_id),
  geom_type text,
  fill_hex text,
  fill_rgb jsonb,
  fill_opacity numeric,
  stroke_hex text,
  stroke_rgb jsonb,
  stroke_opacity numeric,
  stroke_width numeric,
  dash_array jsonb,
  hatch_or_pattern text,
  line_cap text,
  line_join text,
  sample_bbox_page jsonb,
  legend_label_text text,
  legend_label_confidence numeric,
  definition_status text NOT NULL DEFAULT 'candidate',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS up_import.up_text_def (
  up_text_def_id bigserial PRIMARY KEY,
  up_id text NOT NULL REFERENCES up_core.up_def(up_id),
  pdf_source_id bigint REFERENCES up_import.pdf_source(pdf_source_id),
  text_role text NOT NULL,
  regex_pattern text,
  layer text,
  "class" text,
  "type" text,
  up_type_id text REFERENCES up_core.up_type_def(up_type_id),
  font_name text,
  font_size_min numeric,
  font_size_max numeric,
  font_color_hex text,
  rotation numeric,
  bbox_rule jsonb,
  association_strategy text,
  definition_status text NOT NULL DEFAULT 'candidate',
  sample_text text,
  sample_bbox_page jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS up_stg.vector_def_candidate (
  vector_def_candidate_id bigserial PRIMARY KEY,
  up_id text NOT NULL REFERENCES up_core.up_def(up_id),
  pdf_source_id bigint REFERENCES up_import.pdf_source(pdf_source_id),
  legend_crop_id bigint REFERENCES up_import.legend_crop(legend_crop_id),
  source_style_key text NOT NULL,
  fill_hex text,
  fill_rgb jsonb,
  fill_opacity numeric,
  stroke_hex text,
  stroke_rgb jsonb,
  stroke_opacity numeric,
  stroke_width numeric,
  dash_array jsonb,
  hatch_or_pattern text,
  line_cap text,
  line_join text,
  geom_type text,
  z_index integer,
  candidate_layer text,
  candidate_class text,
  candidate_type text,
  candidate_up_type_id text,
  legend_label_text text,
  legend_label_confidence numeric,
  sample_count integer NOT NULL DEFAULT 0,
  sample_bbox_page jsonb,
  candidate_status text NOT NULL DEFAULT 'candidate',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS up_stg.up_text_def_candidate (
  up_text_def_candidate_id bigserial PRIMARY KEY,
  up_id text NOT NULL REFERENCES up_core.up_def(up_id),
  pdf_source_id bigint REFERENCES up_import.pdf_source(pdf_source_id),
  text_role text,
  regex_pattern text,
  sample_text text,
  sample_count integer NOT NULL DEFAULT 0,
  font_name text,
  font_size_min numeric,
  font_size_max numeric,
  font_color_hex text,
  rotation numeric,
  candidate_layer text,
  candidate_class text,
  candidate_type text,
  candidate_status text NOT NULL DEFAULT 'candidate',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS up_stg.vector_stg_candidates (
  candidate_id bigserial PRIMARY KEY,
  up_id text NOT NULL REFERENCES up_core.up_def(up_id),
  pdf_source_id bigint REFERENCES up_import.pdf_source(pdf_source_id),
  pdf_page_id bigint REFERENCES up_import.pdf_page(pdf_page_id),
  algorithm_id text NOT NULL,
  vector_def_id bigint REFERENCES up_import.vector_def(vector_def_id),
  selected_vector_def_id bigint REFERENCES up_import.vector_def(vector_def_id),
  selected_text_def_id bigint REFERENCES up_import.up_text_def(up_text_def_id),
  up_type_id text REFERENCES up_core.up_type_def(up_type_id),
  geom_page geometry(Geometry, 0),
  is_closed boolean,
  source_vector_import_ids bigint[],
  classification_status text NOT NULL,
  confidence numeric,
  diagnostics_json jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS up_stg.vector_stg_single_polygon (
  stg_polygon_id bigserial PRIMARY KEY,
  candidate_id bigint NOT NULL REFERENCES up_stg.vector_stg_candidates(candidate_id) ON DELETE CASCADE,
  up_id text NOT NULL REFERENCES up_core.up_def(up_id),
  up_type_id text REFERENCES up_core.up_type_def(up_type_id),
  fid_temp text,
  geom_page geometry(Polygon, 0) NOT NULL,
  area_page numeric,
  bbox_page jsonb,
  is_closed boolean NOT NULL,
  is_multipolygon_split boolean NOT NULL DEFAULT false,
  split_group_id text,
  confidence numeric,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT vector_stg_single_polygon_type CHECK (GeometryType(geom_page) = 'POLYGON')
);

CREATE TABLE IF NOT EXISTS up_stg.vector_stg_text_assignment (
  text_assignment_id bigserial PRIMARY KEY,
  stg_polygon_id bigint NOT NULL REFERENCES up_stg.vector_stg_single_polygon(stg_polygon_id) ON DELETE CASCADE,
  up_text_def_id bigint REFERENCES up_import.up_text_def(up_text_def_id),
  text_id text,
  source_text text,
  text_bbox_page jsonb,
  assignment_method text,
  assignment_distance numeric,
  confidence numeric,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS up_stg.vector_stg_residual (
  residual_id bigserial PRIMARY KEY,
  up_id text NOT NULL REFERENCES up_core.up_def(up_id),
  up_type_id text REFERENCES up_core.up_type_def(up_type_id),
  validation_mode text,
  residual_type text CHECK (residual_type IN ('missing', 'extra')),
  geom_page geometry(Geometry, 0),
  area_page numeric,
  source_mask_ref text,
  generated_union_ref text,
  confidence numeric,
  requires_manual_review boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS up_stg.class_remap_candidate (
  candidate_id bigserial PRIMARY KEY,
  run_id text NOT NULL,
  vector_def_id bigint REFERENCES up_import.vector_def(vector_def_id),
  up_text_def_id bigint REFERENCES up_import.up_text_def(up_text_def_id),
  raw_layer text,
  raw_class text,
  raw_type_text text,
  proposed_layer text,
  proposed_class text,
  proposed_type text,
  proposed_layer_class text,
  proposed_class_type text,
  matched_rule text,
  match_score numeric,
  requires_manual_review boolean NOT NULL DEFAULT true,
  reason text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS up_manual.vector_review (
  review_id bigserial PRIMARY KEY,
  stg_polygon_id bigint NOT NULL REFERENCES up_stg.vector_stg_single_polygon(stg_polygon_id),
  up_id text NOT NULL REFERENCES up_core.up_def(up_id),
  up_type_id text REFERENCES up_core.up_type_def(up_type_id),
  decision text NOT NULL CHECK (decision IN ('approved', 'rejected', 'corrected', 'needs_more_evidence')),
  corrected_geom_page geometry(Polygon, 0),
  corrected_text_id text,
  comment text,
  reviewed_by text,
  reviewed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS up_manual.polygon_edit_session (
  manual_edit_id bigserial PRIMARY KEY,
  up_id text NOT NULL REFERENCES up_core.up_def(up_id),
  stg_polygon_id bigint REFERENCES up_stg.vector_stg_single_polygon(stg_polygon_id),
  fid text,
  edit_status text NOT NULL DEFAULT 'draft',
  edit_reason text,
  geom_page_before geometry(Polygon, 0) NOT NULL,
  geom_page_after geometry(Polygon, 0) NOT NULL,
  area_before_page_units numeric,
  area_after_page_units numeric,
  area_delta_pct numeric,
  is_closed_after boolean NOT NULL,
  is_valid_after boolean NOT NULL,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT polygon_edit_single_after CHECK (GeometryType(geom_page_after) = 'POLYGON')
);

CREATE TABLE IF NOT EXISTS up_manual.polygon_vertex_edit (
  vertex_edit_id bigserial PRIMARY KEY,
  manual_edit_id bigint NOT NULL REFERENCES up_manual.polygon_edit_session(manual_edit_id) ON DELETE CASCADE,
  operation text NOT NULL,
  vertex_index integer,
  point_before geometry(Point, 0),
  point_after geometry(Point, 0),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS up_manual.polygon_annotation (
  annotation_id bigserial PRIMARY KEY,
  up_id text NOT NULL REFERENCES up_core.up_def(up_id),
  stg_polygon_id bigint REFERENCES up_stg.vector_stg_single_polygon(stg_polygon_id),
  vector_output_id bigint,
  annotation_type text NOT NULL,
  label_text text,
  note_text text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  is_active boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS up_manual.class_remap_override (
  override_id bigserial PRIMARY KEY,
  run_id text NOT NULL,
  target_kind text NOT NULL CHECK (target_kind IN ('vector_def', 'text_def', 'feature', 'profile')),
  target_id text NOT NULL,
  override_layer text NOT NULL,
  override_class text NOT NULL,
  override_type text NOT NULL,
  override_layer_class text NOT NULL,
  override_class_type text NOT NULL,
  override_group text,
  override_label text,
  note text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT class_remap_custom_note CHECK (
    override_layer <> 'CUST' OR (note IS NOT NULL AND override_label IS NOT NULL)
  )
);

CREATE TABLE IF NOT EXISTS up_core.vector_output (
  vector_output_id bigserial PRIMARY KEY,
  up_id text NOT NULL REFERENCES up_core.up_def(up_id),
  up_type_id text NOT NULL REFERENCES up_core.up_type_def(up_type_id),
  fid text NOT NULL,
  layer text NOT NULL,
  "class" text NOT NULL,
  "type" text NOT NULL,
  layer_class text NOT NULL,
  class_type text NOT NULL,
  text_id text,
  geom_page geometry(Polygon, 0) NOT NULL,
  is_closed boolean NOT NULL,
  source_pdf_sha256 text,
  source_page_number integer,
  source_algorithm_id text,
  source_confidence numeric,
  source_stg_polygon_id bigint REFERENCES up_stg.vector_stg_single_polygon(stg_polygon_id),
  manual_edit_id bigint REFERENCES up_manual.polygon_edit_session(manual_edit_id),
  label_override text,
  review_status text NOT NULL DEFAULT 'approved',
  reviewed_by text,
  reviewed_at timestamptz,
  confidence_final numeric,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT vector_output_single_polygon CHECK (GeometryType(geom_page) = 'POLYGON'),
  CONSTRAINT vector_output_no_review_required_core CHECK (review_status <> 'review_required'),
  CONSTRAINT vector_output_class_type CHECK (
    class_type = "class" || '.' ||
    CASE "type"
      WHEN 'STAV' THEN '1'
      WHEN 'NAVRH' THEN '2'
      WHEN 'REZERVA' THEN '3'
      ELSE '0'
    END
  )
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'polygon_annotation_vector_output_fk'
  ) THEN
    ALTER TABLE up_manual.polygon_annotation
      ADD CONSTRAINT polygon_annotation_vector_output_fk
      FOREIGN KEY (vector_output_id)
      REFERENCES up_core.vector_output(vector_output_id);
  END IF;
END $$;

CREATE OR REPLACE VIEW up_api.vector_output_geojson AS
SELECT
  vector_output_id,
  jsonb_build_object(
    'type', 'Feature',
    'id', fid,
    'properties', jsonb_build_object(
      'FID', fid,
      'up_id', up_id,
      'up_type_id', up_type_id,
      'LAYER', layer,
      'CLASS', "class",
      'TYPE', "type",
      'LAYER_CLASS', layer_class,
      'class_type', class_type,
      'text_id', text_id,
      'IS_CLOSED', is_closed,
      'label_override', label_override,
      'review_status', review_status,
      'source_algorithm_id', source_algorithm_id
    ),
    'geometry', ST_AsGeoJSON(geom_page)::jsonb
  ) AS feature
FROM up_core.vector_output;

CREATE OR REPLACE VIEW up_api.review_queue AS
SELECT
  p.stg_polygon_id,
  p.up_id,
  p.up_type_id,
  p.fid_temp,
  c.algorithm_id,
  c.classification_status,
  c.confidence,
  c.diagnostics_json,
  p.geom_page,
  p.area_page,
  p.is_closed
FROM up_stg.vector_stg_single_polygon p
JOIN up_stg.vector_stg_candidates c ON c.candidate_id = p.candidate_id
WHERE c.classification_status IN ('review_required', 'candidate_requires_legend_or_profile_mapping');
