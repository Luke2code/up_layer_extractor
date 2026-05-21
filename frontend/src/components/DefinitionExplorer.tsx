import { Check, Download, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { approveDefinition, exportRecords, generateDefinitionCandidates } from "../lib/api";
import { featureCountByLayerClass, hasMultiPolygon } from "../lib/geo";
import { generateRemapRows, type RemapConfig } from "../lib/remap";
import type { ClassificationProposal, CorrectionTask, DefinitionCandidate, FeatureCollection, GeoFeature, LegendCrop, LegendItem, LegendRow, LegendSymbol, PipelineTrace, RemapResult, StructuredError, TextSpec, VectorSpec, VectorTrace } from "../types";
import { DataTable } from "./DataTable";

type ExplorerTab = "map" | "vector" | "text" | "legend" | "legendRows" | "classification" | "pipeline" | "traces" | "errors" | "diagnostics" | "raw" | "corrections" | "remapping";

interface DefinitionExplorerProps {
  collection: FeatureCollection | null;
  visibleFeatures: GeoFeature[];
  selected: GeoFeature | null;
  remapConfig: RemapConfig | null;
  requestedTab?: string | null;
  focusedLegendItemId?: string | null;
  checkedLegendItemIds?: Set<string>;
  legendReviewStatuses?: Record<string, string>;
}

const tabs: Array<{ id: ExplorerTab; label: string }> = [
  { id: "map", label: "Map Preview" },
  { id: "vector", label: "Vector Definitions" },
  { id: "text", label: "Text Definitions" },
  { id: "legend", label: "Legend Crops" },
  { id: "legendRows", label: "Legend Rows" },
  { id: "classification", label: "Classification" },
  { id: "pipeline", label: "Pipeline" },
  { id: "traces", label: "Trace Logs" },
  { id: "errors", label: "Errors" },
  { id: "diagnostics", label: "Diagnostics" },
  { id: "raw", label: "Raw Objects" },
  { id: "corrections", label: "Corrections" },
  { id: "remapping", label: "Remapping" }
];

const LARGE_COLLECTION_FEATURE_THRESHOLD = 20000;

function localDefinitionCandidates(collection: FeatureCollection): { vector: DefinitionCandidate[]; text: DefinitionCandidate[] } {
  const vector = new Map<string, DefinitionCandidate>();
  const text = new Map<string, DefinitionCandidate>();
  for (const feature of collection.features) {
    const props = feature.properties;
    const styleKey = String(props.style_hex ?? props.source_style_hex ?? "not_exposed");
    const vectorKey = `${styleKey}.${props.LAYER}.${props.CLASS}.${props.TYPE}`;
    if (!vector.has(vectorKey)) {
      vector.set(vectorKey, {
        candidate_id: `local-vector-${vector.size + 1}`,
        source_style_key: styleKey,
        legend_screenprint: props.legend_symbol ?? "not_exposed",
        legend_label_text: props.legend_symbol,
        fill_hex: (props.style_hex ?? props.source_style_hex ?? null) as string | null,
        stroke_hex: (props.source_stroke_hex ?? null) as string | null,
        geom_type: feature.geometry.type,
        sample_count: 1,
        candidate_layer: props.LAYER,
        candidate_class: props.CLASS,
        candidate_type: props.TYPE,
        candidate_status: "candidate"
      });
    } else {
      const current = vector.get(vectorKey);
      if (current) current.sample_count = (current.sample_count ?? 0) + 1;
    }
    if (props.text_id) {
      const textKey = `${props.LAYER}.${props.CLASS}.${props.TYPE}.${props.text_id}`;
      if (!text.has(textKey)) {
        text.set(textKey, {
          candidate_id: `local-text-${text.size + 1}`,
          text_role: props.LAYER === "ZMEN" ? "change_label" : "source_label",
          regex_pattern: "^(Z|P|K)[0-9]+(?:/[0-9]+)?$",
          sample_text: String(props.text_id),
          font_name: "not_exposed",
          association_strategy: "inside_polygon_or_nearest_boundary",
          candidate_layer: props.LAYER,
          candidate_class: props.CLASS,
          candidate_type: props.TYPE,
          candidate_status: "candidate",
          sample_count: 1
        });
      }
    }
  }
  return { vector: [...vector.values()], text: [...text.values()] };
}

export function DefinitionExplorer({
  collection,
  visibleFeatures,
  selected,
  remapConfig,
  requestedTab,
  focusedLegendItemId,
  checkedLegendItemIds = new Set(),
  legendReviewStatuses = {}
}: DefinitionExplorerProps) {
  const [tab, setTab] = useState<ExplorerTab>("map");
  const [vectorDefinitions, setVectorDefinitions] = useState<VectorSpec[]>([]);
  const [textDefinitions, setTextDefinitions] = useState<TextSpec[]>([]);
  const [status, setStatus] = useState("local candidates");
  const [exportStatus, setExportStatus] = useState("");

  useEffect(() => {
    if (!collection) return;
    if (collection.vector_definitions || collection.text_definitions) {
      setVectorDefinitions((collection.vector_definitions ?? collection.vector_specs ?? []) as VectorSpec[]);
      setTextDefinitions((collection.text_definitions ?? collection.text_specs ?? []) as TextSpec[]);
      setStatus(`${collection.source_type ?? "backend"} records`);
      return;
    }
    const local = localDefinitionCandidates(collection);
    setVectorDefinitions(local.vector as VectorSpec[]);
    setTextDefinitions(local.text as TextSpec[]);
    setStatus("local candidates");
    if (collection.features.length > LARGE_COLLECTION_FEATURE_THRESHOLD) {
      setStatus("local candidates; backend skipped for large collection");
      return;
    }
    generateDefinitionCandidates(collection)
      .then((result) => {
        setVectorDefinitions(result.vector_definitions as VectorSpec[]);
        setTextDefinitions(result.text_definitions as TextSpec[]);
        setStatus("backend candidates");
      })
      .catch(() => setStatus("local candidates; backend unavailable"));
  }, [collection]);

  useEffect(() => {
    if (requestedTab?.startsWith("vector")) setTab("vector");
  }, [requestedTab]);

  const remapRows = useMemo<RemapResult[]>(() => {
    if (!remapConfig || !collection) return [];
    return generateRemapRows(collection.features.map((feature) => feature.properties), remapConfig);
  }, [collection, remapConfig]);

  async function approve(candidate: DefinitionCandidate, kind: "vector" | "text") {
    if (candidate.candidate_id.startsWith("local-")) {
      if (kind === "vector") {
        setVectorDefinitions((rows) => rows.map((row) => (row.candidate_id === candidate.candidate_id ? { ...row, candidate_status: "approved" } : row)));
      } else {
        setTextDefinitions((rows) => rows.map((row) => (row.candidate_id === candidate.candidate_id ? { ...row, candidate_status: "approved" } : row)));
      }
      return;
    }
    const approved = await approveDefinition(candidate.candidate_id, kind);
    if (kind === "vector") {
      setVectorDefinitions((rows) => rows.map((row) => (row.candidate_id === approved.candidate_id ? approved as VectorSpec : row)));
    } else {
      setTextDefinitions((rows) => rows.map((row) => (row.candidate_id === approved.candidate_id ? approved as TextSpec : row)));
    }
  }

  const counts = featureCountByLayerClass(visibleFeatures);
  const displayedVectorDefinitions = focusedLegendItemId
    ? vectorDefinitions.filter((row) => row.legend_item_id === focusedLegendItemId)
    : vectorDefinitions;
  const classificationRows = (collection?.classification_proposals ?? []) as ClassificationProposal[];
  const legendRows = (collection?.legend_crops ?? []) as LegendCrop[];
  const legendRowRecords = (collection?.legend_rows ?? []) as LegendRow[];
  const legendItems = (collection?.legend_items ?? []) as LegendItem[];
  const legendSymbols = (collection?.legend_symbols ?? []) as LegendSymbol[];
  const focusedLegendItem = focusedLegendItemId ? legendItems.find((item) => item.legend_item_id === focusedLegendItemId) : null;
  const focusedLegendSymbols = focusedLegendItemId ? legendSymbols.filter((symbol) => symbol.legend_item_id === focusedLegendItemId) : [];
  const focusedLegendReview = focusedLegendItem ? legendReviewStatuses[focusedLegendItem.legend_item_id] ?? focusedLegendItem.review_status ?? "unreviewed" : "unreviewed";
  const focusedLegendChecked = focusedLegendItem ? checkedLegendItemIds.has(focusedLegendItem.legend_item_id) : false;
  const focusedLegendMissing = focusedLegendItem ? Math.max(Number(focusedLegendItem.missing_expected_symbol_count ?? 0), 2 - displayedVectorDefinitions.length) : 0;
  const focusedLegendExportEligible = Boolean(focusedLegendItem && focusedLegendChecked && focusedLegendReview === "approved" && focusedLegendMissing === 0);
  const pipelineRows = (collection?.pipeline_traces ?? []) as PipelineTrace[];
  const vectorTraceRows = (collection?.vector_extraction_traces ?? []) as VectorTrace[];
  const errorRows = (collection?.structured_errors ?? []) as StructuredError[];
  const geometryErrorRows = (collection?.geometry_error_candidates ?? []) as StructuredError[];
  const correctionRows = (collection?.correction_tasks ?? []) as CorrectionTask[];

  async function downloadExport(kind: string) {
    if (!collection) return;
    setExportStatus(`exporting ${kind}`);
    try {
      const result = await exportRecords(collection, kind);
      const url = URL.createObjectURL(new Blob([result.text], { type: "text/plain;charset=utf-8" }));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.filename;
      anchor.click();
      URL.revokeObjectURL(url);
      setExportStatus(`${kind} exported`);
    } catch (error) {
      setExportStatus(`export failed: ${(error as Error).message}`);
    }
  }

  return (
    <div className="min-h-0 bg-white">
      <div className="flex flex-wrap items-center gap-1 border-b border-slate-200 px-2 py-2">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={`rounded-md px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-accent ${
              tab === item.id ? "bg-slate-950 text-white" : "text-slate-700 hover:bg-slate-100"
            }`}
          >
            {item.label}
          </button>
        ))}
        <span className="ml-auto inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-600">
          <RefreshCw className="h-3 w-3" aria-hidden />
          {status}
        </span>
        {collection?.run_id ? <span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600">{collection.run_id}</span> : null}
      </div>
      <div className="thin-scrollbar max-h-[calc(100vh-218px)] overflow-auto p-3">
        {tab === "map" ? (
          <div className="grid gap-2 text-xs">
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                <div className="text-[11px] font-medium uppercase text-slate-500">Current filter</div>
                <div className="mt-1 text-sm font-semibold text-slate-900">{visibleFeatures.length} visible features</div>
              </div>
              <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                <div className="text-[11px] font-medium uppercase text-slate-500">Source</div>
                <div className="mt-1 text-sm font-semibold text-slate-900">{collection?.source_type ?? "local"} / {collection && hasMultiPolygon(collection) ? "MultiPolygon present" : "single Polygon only"}</div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-600 md:grid-cols-6">
              <span>Features: {collection?.feature_count ?? collection?.features.length ?? 0}</span>
              <span>Raw fragments: {collection?.raw_fragment_count ?? collection?.features.length ?? 0}</span>
              <span>Mode: {collection?.primary_extraction_mode ?? "raw/local"}</span>
              <span>Vector defs: {collection?.vector_def_count ?? vectorDefinitions.length}</span>
              <span>Text defs: {collection?.text_def_count ?? textDefinitions.length}</span>
              <span>Legend: {collection?.legend_crop_count ?? legendRows.length} / rows {collection?.legend_row_count ?? legendRowRecords.length}</span>
              <span>Errors: {collection?.error_count ?? errorRows.length}</span>
              <span>Raw debug only: {collection?.raw_features_are_debug_only ? "yes" : "no"}</span>
              <span>Status: {collection?.classification_status ?? "requires_review"}</span>
            </div>
            {collection?.tessellation_metrics ? (
              <div className="grid grid-cols-2 gap-2 rounded-md border border-slate-200 bg-slate-50 p-2 text-[11px] text-slate-700 md:grid-cols-5">
                <span>Tessellated: {collection.tessellation_metrics.tessellated_fill_detected ? "yes" : "no"}</span>
                <span>Score: {String(collection.tessellation_metrics.tessellated_fill_score ?? "n/a")}</span>
                <span>Median area: {String(collection.tessellation_metrics.median_fragment_area ?? "n/a")}</span>
                <span>Tiny ratio: {String(collection.tessellation_metrics.tiny_fragment_ratio ?? "n/a")}</span>
                <span>Tri ratio: {String(collection.tessellation_metrics.triangular_fragment_ratio ?? "n/a")}</span>
              </div>
            ) : null}
            <DataTable
              rows={counts}
              empty="No counts for current filter"
              columns={[
                { key: "key", header: "Layer class / type", render: (row) => row.key },
                { key: "count", header: "Count", render: (row) => row.count, className: "w-20" }
              ]}
            />
          </div>
        ) : null}
        {tab === "vector" ? (
          <div className="grid gap-2">
            {focusedLegendItem ? (
              <div className="grid gap-1 border border-slate-200 bg-slate-50 p-2 text-xs" data-testid="legend-vector-header">
                <div className="font-semibold text-slate-900">Selected legend item: {focusedLegendItem.code_text}</div>
                <div className="flex flex-wrap gap-3 text-slate-700">
                  <span>Expected rows: 1 STAV/STABIL, 2 NAVRH</span>
                  <span>Found rows: {displayedVectorDefinitions.length} / Missing: {focusedLegendMissing}</span>
                  <span>Review: {focusedLegendReview}</span>
                  <span>Checked: {focusedLegendChecked ? "yes" : "no"}</span>
                  <span>Export eligible: {focusedLegendExportEligible ? "yes" : "no"}</span>
                  <span>Symbols: {focusedLegendSymbols.map((symbol) => `${symbol.symbol_order} ${symbol.symbol_role} ${symbol.symbol_status}`).join("; ")}</span>
                </div>
              </div>
            ) : null}
            <button type="button" onClick={() => void downloadExport("vector_definitions")} className="inline-flex w-fit items-center gap-1 rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"><Download className="h-3 w-3" />Export CSV</button>
            <DataTable
              rows={displayedVectorDefinitions}
              empty="No vector definition candidates"
              enableColumnControls
              columns={[
                { key: "status", header: "Select", render: (row) => <button type="button" onClick={() => void approve(row, "vector")} className="inline-flex items-center gap-1 rounded border border-slate-300 px-2 py-1 hover:bg-slate-50"><Check className="h-3 w-3" />{row.candidate_status}</button> },
                { key: "style", header: "Fill / stroke", render: (row) => <span><span className="mr-1 inline-block h-3 w-5 rounded-sm border" style={{ background: row.fill_hex ?? row.fill_color_hex ?? "#fff" }} />{row.fill_hex ?? row.fill_color_hex ?? "null"} / {row.stroke_hex ?? row.stroke_color_hex ?? "null"}</span> },
                { key: "legend", header: "Legend item", render: (row) => row.legend_item_id ? <span>{String(row.code_text ?? row.candidate_class ?? "")}<br />{String(row.symbol_role ?? "")} #{String(row.symbol_order ?? "")}</span> : "none" },
                { key: "class_type", header: "Class type", render: (row) => `${row.class_type ?? row.candidate_type ?? "UNMAPPED"} / ${row.class_type_id ?? "n/a"}` },
                { key: "legend_ids", header: "Legend links", render: (row) => row.legend_item_id ? <span>{String(row.legend_item_id)}<br />{String(row.legend_row_id ?? "no-row")}<br />{String(row.legend_symbol_id ?? "no-symbol")}</span> : "none" },
                { key: "symbol_bbox", header: "Symbol bbox / rect", render: (row) => row.legend_item_id ? `${Array.isArray(row.symbol_bbox_page_pt) ? row.symbol_bbox_page_pt.join(", ") : "missing"} / ${row.source_rect_index ?? "n/a"}` : "none" },
                { key: "checked", header: "Checked / review / export", render: (row) => {
                  const itemId = String(row.legend_item_id ?? "");
                  const review = legendReviewStatuses[itemId] ?? row.review_status ?? "unreviewed";
                  const checked = itemId ? checkedLegendItemIds.has(itemId) : row.is_checked_for_mapping;
                  const exportEligible = checked && review === "approved";
                  return `${checked ? "checked" : "not checked"} / ${review} / ${exportEligible ? "eligible" : "not eligible"}`;
                } },
                { key: "dash", header: "Dash", render: (row) => row.dash_pattern_normalized ?? (row.has_dash_pattern ? "raw" : "none") },
                { key: "path", header: "Path ops", render: (row) => `l=${row.path_item_type_counts?.l ?? 0} c=${row.path_item_type_counts?.c ?? 0} qu=${row.path_item_type_counts?.qu ?? 0} re=${row.path_item_type_counts?.re ?? 0}` },
                { key: "source_layer", header: "Source layer", render: (row) => row.source_layer_name ?? "null" },
                { key: "count", header: "Emitted / samples", render: (row) => `${row.emitted_feature_count ?? 0} / ${row.sample_count ?? 0}` },
                { key: "reject", header: "Rejected reason", render: (row) => row.rejected_reason ?? "none" }
              ]}
            />
          </div>
        ) : null}
        {tab === "text" ? (
          <div className="grid gap-2">
            <button type="button" onClick={() => void downloadExport("text_definitions")} className="inline-flex w-fit items-center gap-1 rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"><Download className="h-3 w-3" />Export CSV</button>
            <DataTable
              rows={textDefinitions}
              empty="No text definition candidates"
              enableColumnControls
              columns={[
                { key: "status", header: "Select", render: (row) => <button type="button" onClick={() => void approve(row, "text")} className="inline-flex items-center gap-1 rounded border border-slate-300 px-2 py-1 hover:bg-slate-50"><Check className="h-3 w-3" />{row.candidate_status}</button> },
                { key: "sample", header: "Text", render: (row) => row.sample_text ?? row.raw_text ?? "null" },
                { key: "match", header: "Matched", render: (row) => row.matched_code_candidate ?? row.matched_label_candidate ?? "none" },
                { key: "font", header: "Font / color", render: (row) => `${row.font_name ?? "not_exposed"} / ${row.text_color_hex ?? "null"}` },
                { key: "score", header: "Scores", render: (row) => `legend=${row.legend_candidate_score ?? 0} class=${row.classification_candidate_score ?? 0}` },
                { key: "reject", header: "Rejected reason", render: (row) => row.rejected_reason ?? "none" }
              ]}
            />
          </div>
        ) : null}
        {tab === "legend" ? (
          <DataTable
            rows={legendRows}
            empty="No legend crop evidence exposed by current source"
            enableColumnControls
            columns={[
              { key: "id", header: "ID", render: (row) => row.legend_crop_id },
              { key: "text", header: "Extracted text", render: (row) => row.extracted_text ?? "unavailable" },
              { key: "matched", header: "Matched", render: (row) => row.matched_code ?? row.matched_label ?? "none" },
              { key: "proposal", header: "Proposal", render: (row) => `${row.proposed_up_layer ?? "null"}.${row.proposed_up_class ?? "null"} / ${row.proposed_up_type ?? "null"}` },
              { key: "artifact", header: "Artifact", render: (row) => row.image_artifact_path_or_url ?? "none" },
              { key: "bbox", header: "BBox", render: (row) => Array.isArray(row.crop_bbox_page_pt) ? row.crop_bbox_page_pt.join(", ") : "none" },
              { key: "status", header: "Status", render: (row) => row.review_status ?? "requires_review" },
              { key: "reason", header: "Unavailable reason", render: (row) => row.unavailable_reason ?? "none" }
            ]}
          />
        ) : null}
        {tab === "legendRows" ? (
          <div className="grid gap-2">
            <button type="button" onClick={() => void downloadExport("legend_rows")} className="inline-flex w-fit items-center gap-1 rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"><Download className="h-3 w-3" />Export CSV</button>
            <DataTable
              rows={legendRowRecords}
              empty="No legend row records"
              enableColumnControls
              columns={[
                { key: "code", header: "Code", render: (row) => row.target_code ?? "none" },
                { key: "group", header: "Group", render: (row) => row.target_group ?? "none" },
                { key: "anchor", header: "Anchor", render: (row) => row.anchor_text ?? "none" },
                { key: "crop", header: "In autocrop", render: (row) => row.anchor_in_autocrop ? "yes" : "no" },
                { key: "occurrences", header: "Map text", render: (row) => row.map_text_occurrence_count ?? 0 },
                { key: "style", header: "Fill / stroke / dash", render: (row) => `${row.matched_fill_hex ?? "null"} / ${row.matched_stroke_hex ?? "null"} / ${row.matched_dash_pattern ?? "solid"}` },
                { key: "confidence", header: "Confidence", render: (row) => row.confidence ?? 0 },
                { key: "status", header: "Status", render: (row) => row.review_status ?? "requires_review" },
                { key: "reason", header: "Reason", render: (row) => row.requires_review_reason ?? "none" }
              ]}
            />
          </div>
        ) : null}
        {tab === "classification" ? (
          <div className="grid gap-2">
            <button type="button" onClick={() => void downloadExport("classification_proposals")} className="inline-flex w-fit items-center gap-1 rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"><Download className="h-3 w-3" />Export CSV</button>
            <DataTable
              rows={classificationRows}
              empty="No classification proposals"
              enableColumnControls
              columns={[
                { key: "target", header: "Target", render: (row) => `${row.proposed_up_layer}.${row.proposed_up_class} / ${row.proposed_up_type}` },
                { key: "raw", header: "Raw", render: (row) => `${row.raw_LAYER}.${row.raw_CLASS} / ${row.raw_TYPE}` },
                { key: "scope", header: "In scope", render: (row) => row.is_inscope_bydleni_related ? "yes" : "no" },
                { key: "confidence", header: "Confidence", render: (row) => row.confidence ?? 0 },
                { key: "review", header: "Review", render: (row) => row.requires_review ? "required" : "not required" },
                { key: "rule", header: "Rule", render: (row) => row.rule_id ?? "none" },
                { key: "reason", header: "Reason", render: (row) => row.rule_reason ?? "none" }
              ]}
            />
          </div>
        ) : null}
        {tab === "pipeline" ? (
          <div className="grid gap-3">
            <div className="flex flex-wrap gap-2">
              {["pipeline_traces", "task_stats", "correction_tasks", "legend_crops", "legend_items", "legend_symbols", "agent_legend_proposals", "raw_fragment_debug_sample"].map((kind) => (
                <button key={kind} type="button" onClick={() => void downloadExport(kind)} className="inline-flex items-center gap-1 rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"><Download className="h-3 w-3" />{kind}</button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
              <span className="rounded-md border border-slate-200 bg-slate-50 p-2">Primary: {collection?.primary_extraction_mode ?? "n/a"}</span>
              <span className="rounded-md border border-slate-200 bg-slate-50 p-2">Raw: {collection?.raw_fragment_count ?? 0}</span>
              <span className="rounded-md border border-slate-200 bg-slate-50 p-2">Features: {collection?.feature_count ?? 0}</span>
              <span className="rounded-md border border-slate-200 bg-slate-50 p-2">Review rows: {String(collection?.task_stats?.requires_review_rows ?? "n/a")}</span>
            </div>
            <DataTable
              rows={pipelineRows}
              empty="No pipeline trace records"
              enableColumnControls
              columns={[
                { key: "order", header: "#", render: (row) => row.step_order, className: "w-12" },
                { key: "step", header: "Step", render: (row) => row.step_name },
                { key: "algorithm", header: "Algorithm", render: (row) => row.algorithm },
                { key: "counts", header: "In / out / rejected", render: (row) => `${row.input_count} / ${row.output_count} / ${row.rejected_count ?? 0}` },
                { key: "warnings", header: "Warnings / errors", render: (row) => `${row.warning_count ?? 0} / ${row.error_count ?? 0}` },
                { key: "runtime", header: "Runtime", render: (row) => `${row.runtime_ms ?? 0} ms` },
                { key: "status", header: "Status", render: (row) => row.status }
              ]}
            />
          </div>
        ) : null}
        {tab === "traces" ? (
          <div className="grid gap-3">
            <div className="flex flex-wrap gap-2">
              {["pipeline_traces", "vector_traces", "text_traces"].map((kind) => (
                <button key={kind} type="button" onClick={() => void downloadExport(kind)} className="inline-flex items-center gap-1 rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"><Download className="h-3 w-3" />{kind}</button>
              ))}
            </div>
            <DataTable
              rows={pipelineRows}
              empty="No pipeline trace records"
              enableColumnControls
              columns={[
                { key: "order", header: "#", render: (row) => row.step_order, className: "w-12" },
                { key: "step", header: "Step", render: (row) => row.step_name },
                { key: "algorithm", header: "Algorithm", render: (row) => row.algorithm },
                { key: "counts", header: "In / out / rejected", render: (row) => `${row.input_count} / ${row.output_count} / ${row.rejected_count ?? 0}` },
                { key: "status", header: "Status", render: (row) => row.status }
              ]}
            />
            <DataTable
              rows={vectorTraceRows}
              empty="No vector trace sample"
              maxRows={300}
              enableColumnControls
              columns={[
                { key: "drawing", header: "Drawing", render: (row) => row.drawing_index ?? "null" },
                { key: "style", header: "Fill / stroke", render: (row) => `${row.fill_color_hex ?? "null"} / ${row.stroke_color_hex ?? "null"}` },
                { key: "dash", header: "Dash", render: (row) => row.dash_pattern_normalized ?? "none" },
                { key: "rings", header: "Rings / holes", render: (row) => `${row.ring_count ?? 0} / ${row.hole_count ?? 0}` },
                { key: "reject", header: "Rejected reason", render: (row) => row.rejected_reason ?? "none" }
              ]}
            />
          </div>
        ) : null}
        {tab === "errors" ? (
          <div className="grid gap-3">
            <button type="button" onClick={() => void downloadExport("structured_errors")} className="inline-flex w-fit items-center gap-1 rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"><Download className="h-3 w-3" />Export CSV</button>
            <DataTable
              rows={errorRows}
              empty="No structured backend errors"
              columns={[
                { key: "step", header: "Step", render: (row) => row.step ?? "unknown" },
                { key: "severity", header: "Severity", render: (row) => row.severity ?? "info" },
                { key: "code", header: "Code", render: (row) => row.error_code ?? "none" },
                { key: "message", header: "Message", render: (row) => row.message ?? "" },
                { key: "action", header: "Recovery", render: (row) => row.recovery_action ?? "requires_review" }
              ]}
            />
            <DataTable
              rows={geometryErrorRows}
              empty="No geometry error candidates"
              columns={[
                { key: "id", header: "ID", render: (row) => String(row.geometry_error_id ?? "") },
                { key: "type", header: "Type", render: (row) => String(row.error_type ?? "") },
                { key: "drawing", header: "Drawing", render: (row) => String(row.drawing_index ?? "") },
                { key: "message", header: "Message", render: (row) => String(row.message ?? "") },
                { key: "status", header: "Status", render: (row) => String(row.review_status ?? "requires_review") }
              ]}
            />
          </div>
        ) : null}
        {tab === "diagnostics" ? (
          <pre className="overflow-auto rounded-md border border-slate-200 bg-slate-950 p-3 text-[11px] leading-relaxed text-slate-100">
            {JSON.stringify(
              {
                collection: collection
                  ? {
                      name: collection.name,
                      coordinate_system: collection.coordinate_system,
                      classification_status: collection.classification_status ?? "regression_sample",
                      selected_algorithm: collection.selected_algorithm ?? "fixture",
                      page_width_pt: collection.page_width_pt,
                      page_height_pt: collection.page_height_pt,
                      feature_count: collection.features.length,
                      run_id: collection.run_id,
                      collection_id: collection.collection_id,
                      source_filename: collection.source_filename,
                      source_type: collection.source_type,
                      source_fingerprint: collection.source_fingerprint,
                      vector_def_count: collection.vector_def_count,
                      text_def_count: collection.text_def_count,
                      legend_crop_count: collection.legend_crop_count,
                      legend_row_count: collection.legend_row_count,
                      raw_fragment_count: collection.raw_fragment_count,
                      primary_extraction_mode: collection.primary_extraction_mode,
                      raw_features_are_debug_only: collection.raw_features_are_debug_only,
                      error_count: collection.error_count,
                      has_multipolygon: hasMultiPolygon(collection)
                    }
                  : null,
                selected: selected?.properties ?? null,
                diagnostics: collection?.diagnostics ?? null,
                tessellation_metrics: collection?.tessellation_metrics ?? null,
                merge_stats: collection?.merge_stats ?? null,
                legend_detection: collection?.legend_detection ?? null,
                task_stats: collection?.task_stats ?? null
              },
              null,
              2
            )}
          </pre>
        ) : null}
        {tab === "raw" ? (
          <pre className="overflow-auto rounded-md border border-slate-200 bg-slate-950 p-3 text-[11px] leading-relaxed text-slate-100">
            {JSON.stringify(
              {
                selected_feature: selected ?? null,
                raw_objects_sample: (collection?.raw_objects as unknown[] | undefined)?.slice(0, 20) ?? [],
                raw_fragment_debug_sample: (collection?.raw_fragment_debug_sample as unknown[] | undefined)?.slice(0, 10) ?? [],
                feature_sample: collection?.features.slice(0, 3) ?? []
              },
              null,
              2
            )}
          </pre>
        ) : null}
        {tab === "corrections" ? (
          <DataTable
            rows={correctionRows}
            empty="No correction task records"
            enableColumnControls
            columns={[
              { key: "id", header: "ID", render: (row) => row.correction_task_id },
              { key: "status", header: "Status", render: (row) => row.status ?? "unknown" },
              { key: "algorithm", header: "Algorithm", render: (row) => row.algorithm ?? "none" },
              { key: "result", header: "Result", render: (row) => row.result ?? "none" }
            ]}
          />
        ) : null}
        {tab === "remapping" ? (
          <DataTable
            rows={remapRows}
            empty="Remapping config not loaded"
            columns={[
              { key: "raw", header: "Raw evidence", render: (row) => `${row.raw_layer}.${row.raw_class} / ${row.raw_type_text ?? "null"}` },
              { key: "canonical", header: "Canonical proposal", render: (row) => `${row.proposed_layer_class} / ${row.proposed_type} / ${row.proposed_class_type}` },
              { key: "group", header: "Group / label", render: (row) => <span>{row.group_label ?? "null"}<br />{row.display_label ?? "requires review"}</span> },
              { key: "rule", header: "Rule", render: (row) => row.matched_rule },
              { key: "review", header: "Review", render: (row) => row.requires_manual_review ? "required" : "not required" }
            ]}
          />
        ) : null}
        {exportStatus ? <div className="mt-2 rounded-md border border-slate-200 bg-slate-50 p-2 text-[11px] text-slate-600">{exportStatus}</div> : null}
      </div>
    </div>
  );
}
