import { Edit3, Plus, Save, Trash2, X } from "lucide-react";
import { useMemo, useState } from "react";

import type { AnnotationRecord, GeoFeature, ManualEditRecord } from "../types";
import { polygonArea, rings } from "../lib/geo";

interface ManualReviewPanelProps {
  selected: GeoFeature | null;
  draftFeature: GeoFeature | null;
  editMode: boolean;
  lastEdit: ManualEditRecord | null;
  annotations: AnnotationRecord[];
  onBeginEdit: () => void;
  onCancelEdit: () => void;
  onSaveEdit: (reason: string, note: string) => Promise<void>;
  onAddVertex: () => void;
  onDeleteVertex: () => void;
  onSaveAnnotation: (payload: { annotation_type: "label" | "note" | "warning" | "decision"; label_text?: string; note_text?: string }) => Promise<void>;
}

function valueRows(feature: GeoFeature | null, keys: string[]) {
  if (!feature) return [];
  const props = feature.properties;
  return keys
    .map((key) => [key, props[key]])
    .filter(([, value]) => value !== null && value !== undefined && value !== "");
}

function artifactFlags(feature: GeoFeature | null) {
  const value = feature?.properties.artifact_flags;
  return Array.isArray(value) ? value.map(String) : [];
}

export function ManualReviewPanel({
  selected,
  draftFeature,
  editMode,
  lastEdit,
  annotations,
  onBeginEdit,
  onCancelEdit,
  onSaveEdit,
  onAddVertex,
  onDeleteVertex,
  onSaveAnnotation
}: ManualReviewPanelProps) {
  const [editReason, setEditReason] = useState("manual boundary correction");
  const [reviewNote, setReviewNote] = useState("");
  const [labelText, setLabelText] = useState("");
  const [noteText, setNoteText] = useState("");
  const [annotationType, setAnnotationType] = useState<"label" | "note" | "warning" | "decision">("note");
  const [status, setStatus] = useState("");
  const rawRows = valueRows(selected, ["FID", "raw_LAYER", "raw_CLASS", "raw_TYPE", "raw_LAYER_CLASS", "LAYER", "CLASS", "TYPE", "LAYER_CLASS", "class_type", "text_id"]);
  const proposalRows = valueRows(selected, ["proposed_LAYER", "proposed_CLASS", "proposed_TYPE", "proposed_LAYER_CLASS", "matched_legend_item_id", "matched_vector_def_id", "display_fill_hex", "display_stroke_hex", "display_color_source", "legend_symbol_fill_hex"]);
  const diagnosticsRows = valueRows(selected, ["classification_status", "classification_reason", "artifact_trust_state", "export_blocking_reason", "geometry_decision", "geometry_decision_reason", "review_required", "artifact_component_count", "component_count_before", "component_count_after", "disconnected_selected_border_component_count", "island_count", "geometry_cleanup_algorithm", "geometry_cleanup_reason", "cleanup_applied", "cleaned_candidate_available", "cleaned_candidate_reason", "cleanup_before_summary", "cleanup_after_summary", "triangular_void_count", "small_void_count", "void_area_ratio", "void_matches_original_plan", "spike_score", "needle_count", "sliver_component_count", "thin_corridor_count", "spike_review_required_count", "compactness_score", "oriented_bbox_aspect_ratio", "small_angle_vertex_count"]);
  const flags = artifactFlags(selected);
  const geometryDecision = selected
    ? String(selected.properties.geometry_decision ?? (flags.length ? "artifact blocked" : "needs review"))
    : "none";
  const geometryReason = selected
    ? String(selected.properties.geometry_decision_reason ?? selected.properties.export_blocking_reason ?? "No selected polygon")
    : "No selected polygon";

  const areaDelta = useMemo(() => {
    if (!selected || !draftFeature) return null;
    const before = polygonArea(selected);
    const after = polygonArea(draftFeature);
    if (!before) return null;
    return Math.abs(after - before) / before * 100;
  }, [draftFeature, selected]);

  async function saveEdit() {
    setStatus("saving edit");
    try {
      await onSaveEdit(editReason, reviewNote);
      setStatus("manual edit saved");
    } catch (error) {
      setStatus(`edit failed: ${(error as Error).message}`);
    }
  }

  async function saveAnnotation() {
    if (!selected) return;
    setStatus("saving annotation");
    try {
      await onSaveAnnotation({
        annotation_type: annotationType,
        label_text: annotationType === "label" ? labelText : undefined,
        note_text: annotationType !== "label" ? noteText : undefined
      });
      setLabelText("");
      setNoteText("");
      setStatus("annotation saved");
    } catch (error) {
      setStatus(`annotation failed: ${(error as Error).message}`);
    }
  }

  return (
    <aside className="thin-scrollbar min-h-0 overflow-auto bg-white">
      <div className="border-b border-slate-200 px-3 py-2">
        <div className="text-sm font-semibold text-slate-900">Selected Polygon Review</div>
        <div className="mt-0.5 text-[11px] text-slate-500">Raw and staging geometry remain immutable; edits are stored as manual correction records.</div>
      </div>
      <div className="space-y-3 p-3">
        {selected ? (
          <div className="grid gap-3">
            <div className={`border px-2 py-2 text-xs ${geometryDecision.includes("blocked") ? "border-red-200 bg-red-50" : geometryDecision.includes("clean") ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
              <div className="flex items-center justify-between gap-2">
                <div className="font-semibold">Geometry: {geometryDecision}</div>
                <div className="font-medium">Export: {selected.properties.export_eligible ? "eligible" : "blocked"}</div>
              </div>
              <div className="mt-1 text-slate-700">{geometryReason}</div>
              <details className="mt-2">
                <summary className="cursor-pointer text-[11px] font-semibold text-slate-700">Evidence</summary>
                <div className="mt-1 grid gap-1 text-[11px] text-slate-700">
                  <div>Flags: {flags.length ? flags.join(", ") : "none"}</div>
                  <div>Components: {String(selected.properties.component_count_before ?? "n/a")} raw / {String(selected.properties.component_count_after ?? "n/a")} staged</div>
                  <div>Artifacts: {String(selected.properties.artifact_component_count ?? 0)} · holes: {String(selected.properties.void_requires_review_count ?? 0)} · slivers: {String(selected.properties.sliver_component_count ?? 0)} · spikes: {String(selected.properties.spike_review_required_count ?? 0)}</div>
                </div>
              </details>
            </div>

            <div className="rounded-md border border-amber-200 bg-amber-50">
              <div className="border-b border-amber-200 px-2 py-2 text-xs font-semibold text-amber-800">Raw immutable fields</div>
              <div className="grid grid-cols-2 gap-2 p-2">
                {rawRows.map(([key, value]) => (
                  <div key={String(key)} className="min-w-0">
                    <div className="text-[10px] font-medium text-amber-700">{String(key)}</div>
                    <div className="break-words text-xs font-semibold text-slate-900">{String(value)}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-md border border-emerald-200 bg-emerald-50">
              <div className="border-b border-emerald-200 px-2 py-2 text-xs font-semibold text-emerald-800">Proposed mapping fields</div>
              <div className="flex items-center gap-2 border-b border-emerald-100 px-2 py-2 text-xs">
                <span className="h-5 w-8 border border-emerald-300" style={{ background: String(selected.properties.display_fill_hex ?? selected.properties.source_style_hex ?? "#fff") }} />
                <span className="font-semibold text-emerald-900">{String(selected.properties.proposed_CLASS ?? "UNMAPPED")}</span>
                <span className="text-emerald-800">{String(selected.properties.classification_reason ?? "no proposal reason")}</span>
              </div>
              <div className="grid grid-cols-2 gap-2 p-2">
                {proposalRows.length ? proposalRows.map(([key, value]) => (
                  <div key={String(key)} className="min-w-0">
                    <div className="text-[10px] font-medium text-emerald-700">{String(key)}</div>
                    <div className="break-words text-xs font-semibold text-slate-900">{String(value)}</div>
                  </div>
                )) : <div className="col-span-2 text-xs text-emerald-800">No proposal fields were attached; explicit unmapped reason should be reviewed.</div>}
              </div>
            </div>

            <div className="rounded-md border border-slate-200 bg-slate-50">
              <div className="border-b border-slate-200 px-2 py-2 text-xs font-semibold text-slate-800">Classification, artifact flags, export block</div>
              <div className="grid gap-2 p-2 text-xs">
                {diagnosticsRows.map(([key, value]) => (
                  <div key={String(key)} className="grid grid-cols-[9rem_minmax(0,1fr)] gap-2">
                    <span className="font-medium text-slate-600">{String(key)}</span>
                    <span className="break-words font-semibold text-slate-900">{String(value)}</span>
                  </div>
                ))}
                <div className="grid grid-cols-[9rem_minmax(0,1fr)] gap-2">
                  <span className="font-medium text-slate-600">artifact_flags</span>
                  <span className="break-words font-semibold text-slate-900">{flags.length ? flags.join(", ") : "none"}</span>
                </div>
                <div className="grid grid-cols-[9rem_minmax(0,1fr)] gap-2">
                  <span className="font-medium text-slate-600">export_eligible</span>
                  <span className="break-words font-semibold text-slate-900">{selected.properties.export_eligible ? "yes" : "no"}</span>
                </div>
                <div className="flex flex-wrap gap-2 pt-1">
                  <button type="button" onClick={() => void onSaveAnnotation({ annotation_type: "decision", note_text: "approved proposed mapping for export review" })} className="rounded border border-slate-300 bg-white px-2 py-1">Approve mapping</button>
                  <button type="button" onClick={() => void onSaveAnnotation({ annotation_type: "decision", note_text: "rejected proposed mapping" })} className="rounded border border-slate-300 bg-white px-2 py-1">Reject mapping</button>
                  <button type="button" onClick={() => void onSaveAnnotation({ annotation_type: "warning", note_text: "marked as artifact requiring geometry review" })} className="rounded border border-slate-300 bg-white px-2 py-1">Mark artifact</button>
                  <button type="button" onClick={() => void onSaveAnnotation({ annotation_type: "note", note_text: "manual geometry cleanup requested" })} className="rounded border border-slate-300 bg-white px-2 py-1">Request cleanup</button>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-md border border-slate-200 bg-slate-50 px-2 py-4 text-center text-xs text-slate-500">No polygon selected</div>
        )}

        <div className="rounded-md border border-slate-200">
          <div className="flex items-center justify-between border-b border-slate-200 px-2 py-2">
            <div className="text-xs font-semibold text-slate-800">Border Edit</div>
            {editMode ? <span className="rounded bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent">editing</span> : null}
          </div>
          <div className="space-y-2 p-2">
            <div className="flex flex-wrap gap-2">
              <button type="button" disabled={!selected || editMode} onClick={onBeginEdit} className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs disabled:opacity-50">
                <Edit3 className="h-3.5 w-3.5" aria-hidden />
                Edit border
              </button>
              <button type="button" disabled={!editMode} onClick={onAddVertex} className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs disabled:opacity-50">
                <Plus className="h-3.5 w-3.5" aria-hidden />
                Add vertex
              </button>
              <button type="button" disabled={!editMode} onClick={onDeleteVertex} className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs disabled:opacity-50">
                <Trash2 className="h-3.5 w-3.5" aria-hidden />
                Delete vertex
              </button>
            </div>
            <label className="grid gap-1 text-xs">
              <span className="font-medium text-slate-600">Reason</span>
              <input value={editReason} onChange={(event) => setEditReason(event.target.value)} className="rounded-md border border-slate-300 px-2 py-1 outline-none focus:ring-2 focus:ring-accent" />
            </label>
            <label className="grid gap-1 text-xs">
              <span className="font-medium text-slate-600">Review note</span>
              <textarea value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} rows={2} className="resize-none rounded-md border border-slate-300 px-2 py-1 outline-none focus:ring-2 focus:ring-accent" />
            </label>
            {editMode && draftFeature ? (
              <div className="rounded-md border border-slate-200 bg-slate-50 p-2 text-[11px] text-slate-600">
                Vertices: {rings(draftFeature)[0]?.length ?? 0}; area delta: {areaDelta === null ? "n/a" : `${areaDelta.toFixed(2)}%`}
              </div>
            ) : null}
            <div className="flex gap-2">
              <button type="button" disabled={!editMode} onClick={() => void saveEdit()} className="inline-flex items-center gap-1 rounded-md border border-accent bg-accent px-2 py-1 text-xs font-medium text-white disabled:opacity-50">
                <Save className="h-3.5 w-3.5" aria-hidden />
                Save edit
              </button>
              <button type="button" disabled={!editMode} onClick={onCancelEdit} className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs disabled:opacity-50">
                <X className="h-3.5 w-3.5" aria-hidden />
                Cancel
              </button>
            </div>
            {lastEdit ? <div className="rounded-md border border-emerald-200 bg-emerald-50 p-2 text-[11px] text-emerald-800">Last edit {lastEdit.manual_edit_id}: delta {lastEdit.area_delta_pct.toFixed(2)}%</div> : null}
          </div>
        </div>

        <div className="rounded-md border border-slate-200">
          <div className="border-b border-slate-200 px-2 py-2 text-xs font-semibold text-slate-800">Labels, Notes, Warnings</div>
          <div className="space-y-2 p-2">
            <select value={annotationType} onChange={(event) => setAnnotationType(event.target.value as "label" | "note" | "warning" | "decision")} className="w-full rounded-md border border-slate-300 px-2 py-1 text-xs outline-none focus:ring-2 focus:ring-accent">
              <option value="note">Note</option>
              <option value="label">Label</option>
              <option value="warning">Warning</option>
              <option value="decision">Decision</option>
            </select>
            {annotationType === "label" ? (
              <input value={labelText} onChange={(event) => setLabelText(event.target.value)} placeholder="Manual display label" className="w-full rounded-md border border-slate-300 px-2 py-1 text-xs outline-none focus:ring-2 focus:ring-accent" />
            ) : (
              <textarea value={noteText} onChange={(event) => setNoteText(event.target.value)} rows={2} placeholder="Operator note" className="w-full resize-none rounded-md border border-slate-300 px-2 py-1 text-xs outline-none focus:ring-2 focus:ring-accent" />
            )}
            <button type="button" disabled={!selected} onClick={() => void saveAnnotation()} className="rounded-md border border-slate-300 px-2 py-1 text-xs disabled:opacity-50">
              Save annotation
            </button>
            <div className="space-y-1">
              {annotations.length ? (
                annotations.map((annotation) => (
                  <div key={annotation.annotation_id} className="rounded-md border border-slate-200 bg-slate-50 p-2 text-[11px]">
                    <b>{annotation.annotation_type}</b>: {annotation.label_text ?? annotation.note_text}
                  </div>
                ))
              ) : (
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2 text-[11px] text-slate-500">No annotations saved for this session.</div>
              )}
            </div>
          </div>
        </div>

        {status ? <div className="rounded-md border border-slate-200 bg-slate-50 p-2 text-[11px] text-slate-600">{status}</div> : null}
      </div>
    </aside>
  );
}
