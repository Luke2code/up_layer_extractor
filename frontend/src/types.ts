export type Coordinate = [number, number];
export type Ring = Coordinate[];

export interface FeatureProperties {
  FID?: number | string;
  up_id?: string | null;
  up_type_id?: string | null;
  LAYER?: string;
  CLASS?: string;
  TYPE?: string;
  LAYER_CLASS?: string;
  class_type?: string;
  text_id?: string | null;
  IS_CLOSED?: boolean;
  confidence?: string;
  style_hex?: string | null;
  source_style_hex?: string | null;
  source_stroke_hex?: string | null;
  legend_symbol?: string | null;
  bbox_page_pt?: number[];
  note?: string;
  [key: string]: unknown;
}

export interface GeoFeature {
  type: "Feature";
  id?: string | number;
  properties: FeatureProperties;
  geometry: {
    type: "Polygon" | "MultiPolygon";
    coordinates: Ring[] | Ring[][];
  };
}

export interface FeatureCollection {
  type: "FeatureCollection";
  name?: string;
  run_id?: string;
  collection_id?: string;
  source_filename?: string | null;
  source_url?: string | null;
  source_type?: string;
  source_fingerprint?: string;
  page_width_pt?: number;
  page_height_pt?: number;
  coordinate_system?: string;
  classification_status?: string;
  selected_algorithm?: string;
  diagnostics?: Record<string, unknown>;
  feature_count?: number;
  vector_def_count?: number;
  text_def_count?: number;
  legend_crop_count?: number;
  legend_row_count?: number;
  raw_fragment_count?: number;
  primary_extraction_mode?: string;
  raw_features_are_debug_only?: boolean;
  tessellation_metrics?: Record<string, unknown>;
  fragment_role_stats?: Record<string, unknown>;
  merge_stats?: Record<string, unknown>;
  artifact_diagnostics?: Record<string, unknown>;
  up_extraction_profile?: ExtractionProfile;
  extraction_experiments?: ExtractionExperiment[];
  algorithm_lab_result?: Record<string, unknown>;
  vector_evidence_index_summary?: Record<string, unknown>;
  target_case_v8_3?: Record<string, unknown>;
  experiment_candidate_geometries?: GeoFeature[];
  manual_split_fallbacks?: Record<string, unknown>[];
  feature_proposal_stats?: Record<string, unknown>;
  task_stats?: Record<string, unknown>;
  correction_tasks?: CorrectionTask[];
  error_count?: number;
  source_detection?: SourceDetection;
  plan_snapshot_available?: boolean;
  plan_snapshot_artifact_path?: string | null;
  plan_snapshot_url?: string | null;
  plan_snapshot_source?: string | null;
  plan_snapshot_scale?: Record<string, number> | null;
  plan_snapshot_page_number?: number | null;
  plan_snapshot_transform?: Record<string, unknown> | null;
  plan_snapshot_width_px?: number | null;
  plan_snapshot_height_px?: number | null;
  sample_legend_crop_available?: boolean;
  legend_crop_source?: string | null;
  legend_unavailable_reason?: string | null;
  vector_definitions?: VectorSpec[];
  vector_specs?: VectorSpec[];
  text_definitions?: TextSpec[];
  text_specs?: TextSpec[];
  legend_crops?: LegendCrop[];
  legend_rows?: LegendRow[];
  legend_items?: LegendItem[];
  legend_symbols?: LegendSymbol[];
  legend_mapping_stats?: Record<string, unknown>;
  agent_legend_proposals?: Record<string, unknown>[];
  classification_proposals?: ClassificationProposal[];
  classification_traces?: ClassificationProposal[];
  pipeline_traces?: PipelineTrace[];
  vector_extraction_traces?: VectorTrace[];
  text_extraction_traces?: TextSpec[];
  structured_errors?: StructuredError[];
  geometry_error_candidates?: GeometryErrorCandidate[];
  features: GeoFeature[];
  [key: string]: unknown;
}

export interface Filters {
  LAYER: string;
  CLASS: string;
  TYPE: string;
  IS_CLOSED: string;
}

export interface DefinitionCandidate {
  candidate_id: string;
  source_style_key?: string;
  legend_screenprint?: string;
  legend_label_text?: string | null;
  fill_hex?: string | null;
  stroke_hex?: string | null;
  stroke_width?: number | null;
  dash_array?: unknown;
  fill_opacity?: number | null;
  hatch_or_pattern?: string | null;
  geom_type?: string;
  z_index?: number | null;
  sample_count?: number;
  candidate_layer?: string;
  candidate_class?: string;
  candidate_type?: string;
  mapping?: RemapResult;
  candidate_status?: string;
  text_role?: string;
  regex_pattern?: string;
  sample_text?: string | null;
  font_name?: string | null;
  association_strategy?: string;
  [key: string]: unknown;
}

export interface SourceDetection {
  source_type?: string;
  detection_algorithm?: string;
  page_count?: number | null;
  drawing_count?: number;
  image_count?: number;
  text_span_count?: number;
  has_vector_drawings?: boolean;
  has_images?: boolean;
  has_text?: boolean;
  is_probably_scanned?: boolean;
  is_mixed_pdf?: boolean;
  confidence?: number;
  reason?: string;
  warnings?: string[];
  [key: string]: unknown;
}

export interface VectorSpec extends DefinitionCandidate {
  vector_def_id?: string;
  run_id?: string;
  collection_id?: string;
  source_pdf?: string | null;
  source_fingerprint?: string;
  drawing_index?: number | null;
  drawing_group_id?: string;
  path_item_type_counts?: Record<string, number>;
  fill_color_hex?: string | null;
  stroke_color_hex?: string | null;
  has_l?: boolean;
  has_c?: boolean;
  has_qu?: boolean;
  has_re?: boolean;
  has_dash_pattern?: boolean;
  dash_pattern_raw?: unknown;
  dash_pattern_normalized?: string | null;
  source_layer_name?: string | null;
  emitted_feature_count?: number;
  rejected_reason?: string | null;
  sample_feature_ids?: string[];
}

export interface TextSpec extends DefinitionCandidate {
  text_def_id?: string;
  raw_text?: string;
  normalized_text?: string;
  text_color_hex?: string | null;
  bbox_page_pt?: number[] | null;
  matched_code_candidate?: string | null;
  matched_label_candidate?: string | null;
  legend_candidate_score?: number;
  classification_candidate_score?: number;
  rejected_reason?: string | null;
}

export interface LegendCrop {
  legend_crop_id: string;
  extracted_text?: string | null;
  matched_label?: string | null;
  matched_code?: string | null;
  matched_fill_hex?: string | null;
  matched_stroke_hex?: string | null;
  matched_dash_pattern?: string | null;
  proposed_up_layer?: string | null;
  proposed_up_class?: string | null;
  proposed_up_type?: string | null;
  confidence?: number;
  review_status?: string;
  unavailable_reason?: string | null;
  image_artifact_path_or_url?: string | null;
  image_artifact_url?: string | null;
  image_width_px?: number | null;
  image_height_px?: number | null;
  crop_bbox_page_pt?: number[] | null;
  page_to_image_transform?: Record<string, number> | null;
  [key: string]: unknown;
}

export interface LegendRow {
  legend_row_id: string;
  target_code?: string;
  code_text?: string;
  legend_item_id?: string;
  row_bbox_image_px?: number[] | null;
  row_bbox_page_pt?: number[] | null;
  label_text_raw?: string | null;
  normal_vector_def_row_count?: number;
  missing_expected_symbol_count?: number;
  ignored_extra_symbol_count?: number;
  matched_vector_def_ids?: string[];
  is_checked_for_mapping?: boolean;
  export_eligible?: boolean;
  target_group?: string | null;
  anchor_text?: string | null;
  anchor_in_autocrop?: boolean;
  map_text_occurrence_count?: number;
  matched_fill_hex?: string | null;
  matched_stroke_hex?: string | null;
  matched_dash_pattern?: string | null;
  confidence?: number;
  review_status?: string;
  requires_review_reason?: string | null;
  [key: string]: unknown;
}

export interface LegendItem {
  legend_item_id: string;
  legend_row_id?: string;
  legend_crop_id?: string;
  code_text?: string;
  label_text_raw?: string | null;
  label_text_decoded?: string | null;
  label_text_display?: string | null;
  label_text_status?: string | null;
  label_text_confidence?: number | null;
  label_text_source?: string | null;
  label_text_review_required?: boolean;
  label_text_reason?: string | null;
  row_bbox_image_px?: number[] | null;
  row_bbox_page_pt?: number[] | null;
  symbol_split_status?: string;
  is_checked_for_mapping?: boolean;
  review_status?: string;
  export_eligible?: boolean;
  normal_vector_def_row_count?: number;
  missing_expected_symbol_count?: number;
  ignored_extra_symbol_count?: number;
  matched_vector_def_ids?: string[];
  [key: string]: unknown;
}

export interface LegendLabelCorrectionRecord {
  legend_label_correction_id: string;
  legend_item_id?: string | null;
  original_raw_label?: string | null;
  corrected_label?: string | null;
  reason?: string | null;
  created_by?: string | null;
  created_at?: string | null;
  review_status?: string;
}

export interface LegendSymbol {
  legend_symbol_id: string;
  legend_item_id?: string;
  legend_row_id?: string;
  legend_crop_id?: string;
  symbol_order?: number;
  symbol_role?: string;
  symbol_bbox_image_px?: number[] | null;
  symbol_bbox_page_pt?: number[] | null;
  symbol_fill_hex?: string | null;
  symbol_stroke_hex?: string | null;
  symbol_status?: string;
  review_status?: string;
  [key: string]: unknown;
}

export interface CorrectionTask {
  correction_task_id: string;
  status?: string;
  algorithm?: string;
  result?: string;
  [key: string]: unknown;
}

export interface ExtractionMethodRow {
  method: string;
  czech_explanation?: string;
  status?: string;
  success_rate?: number | null;
  used_for_candidate?: boolean;
  main_evidence?: string;
  main_risk?: string;
  [key: string]: unknown;
}

export interface ExtractionProfile {
  pdf_name?: string | null;
  algorithm?: string;
  methods_attempted?: string[];
  methods_used_for_candidate?: string[];
  methods_rejected?: Array<Record<string, unknown>>;
  method_rows?: ExtractionMethodRow[];
  overall_confidence?: string;
  export_status?: string;
  manual_split_required_count?: number;
  hatch_candidate_count?: number;
  dotted_boundary_candidate_count?: number;
  thick_boundary_candidate_count?: number;
  text_anchor_count?: number;
  export_blocked_feature_count?: number;
  [key: string]: unknown;
}

export interface ExtractionExperiment {
  id: string;
  name?: string;
  approach?: string;
  status?: string;
  score?: number | null;
  confidence?: string;
  metrics?: Record<string, unknown>;
  result_summary?: string;
  learned?: string;
  keep_or_reject?: string;
  artifacts?: string[];
  [key: string]: unknown;
}

export interface PipelineTrace {
  step_order: number;
  step_name: string;
  algorithm: string;
  input_count: number;
  output_count: number;
  skipped_count?: number;
  rejected_count?: number;
  warning_count?: number;
  error_count?: number;
  runtime_ms?: number;
  status: string;
  [key: string]: unknown;
}

export interface VectorTrace {
  trace_id?: string;
  drawing_index?: number;
  fill_color_hex?: string | null;
  stroke_color_hex?: string | null;
  dash_pattern_normalized?: string | null;
  source_layer_name?: string | null;
  ring_count?: number;
  hole_count?: number;
  rejected_reason?: string | null;
  emitted_feature_id?: string | null;
  [key: string]: unknown;
}

export interface ClassificationProposal {
  classification_trace_id?: string;
  vector_def_id?: string;
  text_def_id?: string | null;
  feature_id?: string | null;
  raw_LAYER?: string | null;
  raw_CLASS?: string | null;
  raw_TYPE?: string | null;
  proposed_up_layer?: string;
  proposed_up_class?: string;
  proposed_up_type?: string;
  is_inscope_bydleni_related?: boolean;
  confidence?: number;
  rule_id?: string;
  rule_reason?: string;
  requires_review?: boolean;
  evidence_dash_pattern?: boolean;
  evidence_text_label?: boolean;
  evidence_legend_crop?: boolean;
  [key: string]: unknown;
}

export interface StructuredError {
  step?: string;
  algorithm?: string;
  severity?: string;
  error_code?: string;
  message?: string;
  exception_type?: string | null;
  recovery_action?: string;
  retryable?: boolean;
  [key: string]: unknown;
}

export interface GeometryErrorCandidate {
  geometry_error_id?: string;
  error_type?: string;
  drawing_index?: number;
  bbox_page_pt?: number[] | null;
  message?: string;
  review_status?: string;
  [key: string]: unknown;
}

export interface RemapResult {
  raw_layer?: string | null;
  raw_class?: string | null;
  raw_type_text?: string | null;
  proposed_layer: string;
  proposed_class: string;
  proposed_type: string;
  proposed_layer_class: string;
  proposed_class_type: string;
  group_label?: string | null;
  display_label?: string | null;
  matched_rule: string;
  match_score: number;
  requires_manual_review: boolean;
  reason: string;
}

export interface ManualEditRecord {
  manual_edit_id: string;
  area_delta_pct: number;
  is_closed_after: boolean;
  is_valid_after: boolean;
  edit_status: string;
}

export interface AnnotationRecord {
  annotation_id: string;
  annotation_type: string;
  label_text?: string | null;
  note_text?: string | null;
}
