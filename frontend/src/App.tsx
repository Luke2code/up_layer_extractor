import { useEffect, useMemo, useState, type PointerEvent as ReactPointerEvent } from "react";

import { DefinitionExplorer } from "./components/DefinitionExplorer";
import { IntakeBar } from "./components/IntakeBar";
import { LegendPreview } from "./components/LegendPreview";
import { ManualReviewPanel } from "./components/ManualReviewPanel";
import { MapPreview } from "./components/MapPreview";
import type { MapColorMode } from "./components/MapPreview";
import { Toolbar } from "./components/Toolbar";
import { loadSample, saveAnnotation, saveManualEdit } from "./lib/api";
import { closeRing, cloneFeature, DEFAULT_FILTERS, normalizeFeatureCollection, PAGE, passesFilter, reconcileFilters, rings, updateOuterRing } from "./lib/geo";
import type { AnnotationRecord, FeatureCollection, Filters, GeoFeature, ManualEditRecord } from "./types";
import type { RemapConfig } from "./lib/remap";

const DEFAULT_TOGGLES = {
  plan: true,
  polygons: true,
  validation: false,
  selectedBorder: true,
  textLabel: false,
  fidLabel: false,
  classLabel: false,
  selectedLabel: true
};

const LARGE_COLLECTION_FEATURE_THRESHOLD = 20000;
const REVIEW_MIN_WIDTH = 280;
const REVIEW_MAX_WIDTH = 720;
const RESULTS_MIN_HEIGHT = 18;
const RESULTS_MAX_HEIGHT = 62;
const DEFAULT_LAYOUT = {
  rightWidth: 390,
  bottomHeight: 34,
  reviewHidden: false,
  resultsHidden: false
};

type LayoutState = typeof DEFAULT_LAYOUT;

function loadLayout(): LayoutState {
  try {
    return { ...DEFAULT_LAYOUT, ...JSON.parse(localStorage.getItem("up-layer-layout") ?? "{}") };
  } catch {
    return DEFAULT_LAYOUT;
  }
}

function selectedId(feature: GeoFeature | null) {
  return feature ? String(feature.id ?? feature.properties.FID) : "";
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function insertDefaultVertex(feature: GeoFeature): GeoFeature {
  const ring = rings(feature)[0];
  if (!ring || ring.length < 3) return feature;
  const insertAt = Math.max(1, ring.length - 1);
  const prev = ring[insertAt - 1];
  const first = ring[0];
  const nextPoint: [number, number] = [(prev[0] + first[0]) / 2, (prev[1] + first[1]) / 2];
  return updateOuterRing(feature, [...ring.slice(0, insertAt), nextPoint, ...ring.slice(insertAt)]);
}

function deleteLastEditableVertex(feature: GeoFeature): GeoFeature {
  const ring = rings(feature)[0];
  if (!ring || ring.length <= 4) return feature;
  return updateOuterRing(feature, [...ring.slice(0, ring.length - 2), ring[ring.length - 1]]);
}

export function App() {
  const [collection, setCollection] = useState<FeatureCollection | null>(null);
  const [sourceLabel, setSourceLabel] = useState("Kvetnice bundled sample");
  const [remapConfig, setRemapConfig] = useState<RemapConfig | null>(null);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [selected, setSelected] = useState<GeoFeature | null>(null);
  const [draftFeature, setDraftFeature] = useState<GeoFeature | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [overlay, setOverlay] = useState(0.25);
  const [colorMode, setColorMode] = useState<MapColorMode>("source");
  const [toggles, setToggles] = useState(DEFAULT_TOGGLES);
  const [layout, setLayout] = useState<LayoutState>(() => loadLayout());
  const [lastEdit, setLastEdit] = useState<ManualEditRecord | null>(null);
  const [annotations, setAnnotations] = useState<AnnotationRecord[]>([]);
  const [mainView, setMainView] = useState<"up" | "legend">("up");
  const [detailTabRequest, setDetailTabRequest] = useState<string | null>(null);
  const [focusedLegendItemId, setFocusedLegendItemId] = useState<string | null>(null);
  const [checkedLegendItemIds, setCheckedLegendItemIds] = useState<Set<string>>(() => new Set());
  const [legendReviewStatuses, setLegendReviewStatuses] = useState<Record<string, string>>({});

  useEffect(() => {
    loadSample().then((sample) => {
      const normalized = normalizeFeatureCollection(sample);
      setCollection(normalized);
      setSelected(normalized.features[0] ?? null);
    });
    fetch("/vector_layer_class_type_remap.json")
      .then((response) => response.json() as Promise<RemapConfig>)
      .then(setRemapConfig)
      .catch(() => setRemapConfig(null));
  }, []);

  useEffect(() => {
    localStorage.setItem("up-layer-layout", JSON.stringify(layout));
  }, [layout]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setSelected(null);
        setDraftFeature(null);
        setEditMode(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const features = collection?.features ?? [];
  const pageSize = {
    width: collection?.page_width_pt ?? PAGE.width,
    height: collection?.page_height_pt ?? PAGE.height
  };
  const planImageUrl = collection?.plan_snapshot_url ?? (collection?.name?.toLowerCase().includes("kvetnice") || sourceLabel.toLowerCase().includes("kvetnice") ? "/kvetnice_plan.jpg" : null);
  const hasPlanImage = Boolean(planImageUrl);
  const planSource = collection?.plan_snapshot_available
    ? String(collection.plan_snapshot_source ?? "pdf_page_render")
    : hasPlanImage
      ? "embedded_raster"
      : "unavailable";
  const reconciledFilters = useMemo(() => reconcileFilters(features, filters), [features, filters]);
  const visibleFeatures = useMemo(() => features.filter((feature) => passesFilter(feature, reconciledFilters)), [features, reconciledFilters]);

  function loadCollection(next: FeatureCollection, label: string) {
    setCollection(next);
    setSourceLabel(label);
    setFilters(DEFAULT_FILTERS);
    setSelected(next.features[0] ?? null);
    setDraftFeature(null);
    setEditMode(false);
    setLastEdit(null);
    setAnnotations([]);
    setMainView("up");
    setDetailTabRequest(null);
    setFocusedLegendItemId(null);
    setCheckedLegendItemIds(new Set());
    setLegendReviewStatuses({});
    setColorMode("source");
    setToggles((current) => ({
      ...current,
      plan: Boolean(next.plan_snapshot_url || next.name?.toLowerCase().includes("kvetnice") || label.toLowerCase().includes("kvetnice")),
      validation: current.validation && next.features.length <= LARGE_COLLECTION_FEATURE_THRESHOLD,
      textLabel: false,
      fidLabel: false,
      classLabel: false,
      selectedLabel: true
    }));
  }

  function updateFilter(key: keyof Filters, value: string) {
    setFilters((current) => {
      const next = { ...current, [key]: value };
      if (key === "LAYER") {
        next.CLASS = "ALL";
        next.TYPE = "ALL";
      }
      if (key === "CLASS") {
        next.TYPE = "ALL";
      }
      return next;
    });
    setSelected(null);
    setDraftFeature(null);
    setEditMode(false);
  }

  function beginEdit() {
    if (!selected) return;
    setDraftFeature(cloneFeature(selected));
    setEditMode(true);
  }

  async function saveEdit(reason: string, note: string) {
    if (!selected || !draftFeature) return;
    const record = await saveManualEdit({
      up_id: String(selected.properties.up_id ?? "kvetnice-regression"),
      stg_polygon_id: String(selected.id ?? selected.properties.FID ?? "local-selected"),
      fid: typeof selected.properties.FID === "number" ? selected.properties.FID : undefined,
      edit_reason: reason,
      geom_page_before: selected.geometry,
      geom_page_after: draftFeature.geometry,
      created_by: "operator-ui",
      review_note: note || undefined
    });
    setLastEdit(record);
    setSelected(draftFeature);
    setDraftFeature(null);
    setEditMode(false);
    setCollection((current) => {
      if (!current) return current;
      return {
        ...current,
        features: current.features.map((feature) => (selectedId(feature) === selectedId(selected) ? draftFeature : feature))
      };
    });
  }

  async function createAnnotation(payload: { annotation_type: "label" | "note" | "warning" | "decision"; label_text?: string; note_text?: string }) {
    if (!selected) return;
    try {
      const record = await saveAnnotation({
        up_id: String(selected.properties.up_id ?? "kvetnice-regression"),
        stg_polygon_id: String(selected.id ?? selected.properties.FID ?? "local-selected"),
        ...payload,
        created_by: "operator-ui"
      });
      setAnnotations((current) => [record, ...current]);
    } catch {
      setAnnotations((current) => [
        {
          annotation_id: `local-${current.length + 1}`,
          annotation_type: payload.annotation_type,
          label_text: payload.label_text,
          note_text: payload.note_text
        },
        ...current
      ]);
    }
  }

  function addVertex() {
    if (!draftFeature) return;
    setDraftFeature(insertDefaultVertex(draftFeature));
  }

  function deleteVertex() {
    if (!draftFeature) return;
    setDraftFeature(deleteLastEditableVertex(draftFeature));
  }

  function focusLegendItem(itemId: string) {
    setFocusedLegendItemId(itemId);
    setDetailTabRequest(`vector:${itemId}:${Date.now()}`);
  }

  function toggleLegendItem(itemId: string) {
    setCheckedLegendItemIds((current) => {
      const next = new Set(current);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
    setDetailTabRequest(`vector:${itemId}:${Date.now()}`);
  }

  function beginReviewResize(event: ReactPointerEvent<HTMLDivElement>) {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = layout.rightWidth;
    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    function onPointerMove(moveEvent: PointerEvent) {
      const maxWidth = Math.min(REVIEW_MAX_WIDTH, window.innerWidth - 360);
      const nextWidth = clamp(startWidth - (moveEvent.clientX - startX), REVIEW_MIN_WIDTH, Math.max(REVIEW_MIN_WIDTH, maxWidth));
      setLayout((current) => ({ ...current, rightWidth: nextWidth }));
    }

    function onPointerUp() {
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerUp);
    }

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerUp);
  }

  function beginResultsResize(event: ReactPointerEvent<HTMLDivElement>) {
    event.preventDefault();
    const startY = event.clientY;
    const startHeight = layout.bottomHeight;
    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;
    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";

    function onPointerMove(moveEvent: PointerEvent) {
      const deltaVh = ((moveEvent.clientY - startY) / Math.max(window.innerHeight, 1)) * 100;
      const nextHeight = clamp(startHeight - deltaVh, RESULTS_MIN_HEIGHT, RESULTS_MAX_HEIGHT);
      setLayout((current) => ({ ...current, bottomHeight: nextHeight }));
    }

    function onPointerUp() {
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerUp);
    }

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerUp);
  }

  return (
    <div className="flex h-screen min-h-0 flex-col bg-slate-100 text-slate-900">
      <IntakeBar collection={collection} sourceLabel={sourceLabel} onLoad={loadCollection} onResetLayout={() => setLayout(DEFAULT_LAYOUT)} />
      <Toolbar
        features={features}
        visibleCount={visibleFeatures.length}
        filters={reconciledFilters}
        overlay={overlay}
        toggles={toggles}
        planAvailable={hasPlanImage}
        planSource={planSource}
        colorMode={colorMode}
        onFilterChange={updateFilter}
        onOverlayChange={setOverlay}
        onColorModeChange={setColorMode}
        onToggleChange={(key, value) => setToggles((current) => ({ ...current, [key]: value }))}
        onResetView={() => {
          setSelected(null);
          setDraftFeature(null);
          setEditMode(false);
        }}
      />
      <div
        className="grid min-h-0 flex-1"
        style={{ gridTemplateColumns: layout.reviewHidden ? "minmax(0,1fr)" : `minmax(0,1fr) 1px ${layout.rightWidth}px` }}
      >
        <div
          className="grid min-h-0"
          style={{ gridTemplateRows: layout.resultsHidden ? "minmax(0,1fr)" : `minmax(0,1fr) 1px minmax(12rem,${layout.bottomHeight}vh)` }}
        >
          <div className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] bg-white">
            <div className="flex items-center border-b border-slate-200 bg-white text-sm">
              <button
                type="button"
                onClick={() => setMainView("up")}
                className={`border-r border-slate-200 px-4 py-2 ${mainView === "up" ? "bg-slate-100 font-semibold text-slate-950" : "text-slate-700 hover:bg-slate-50"}`}
              >
                UP
              </button>
              <button
                type="button"
                onClick={() => setMainView("legend")}
                className={`border-r border-slate-200 px-4 py-2 ${mainView === "legend" ? "bg-slate-100 font-semibold text-slate-950" : "text-slate-700 hover:bg-slate-50"}`}
              >
                Legend
              </button>
              <span className="ml-auto px-3 text-xs text-slate-600">
                {collection?.primary_extraction_mode ?? "sample"} · raw {collection?.raw_fragment_count ?? features.length} · merged {collection?.feature_count ?? features.length}
                {" · "}Plan {toggles.plan && hasPlanImage ? "on" : "off"}
                {" · "}Plan source: {planSource}
                {" · "}Polygons {toggles.polygons ? "on" : "off"}
                {" · "}Raster validation {toggles.validation ? "on" : "off"}
                {" · "}Raw debug {collection?.raw_features_are_debug_only ? "on" : "off"}
              </span>
            </div>
            {mainView === "up" ? (
              <MapPreview
                features={visibleFeatures}
                selected={selected}
                draftFeature={draftFeature}
                editMode={editMode}
                pageSize={pageSize}
                showPlanImage={toggles.plan && hasPlanImage}
                planImageUrl={planImageUrl}
                experimentCandidates={collection?.experiment_candidate_geometries ?? []}
                colorMode={colorMode}
                overlay={overlay}
                toggles={toggles}
                onSelect={(feature) => {
                  setSelected(feature);
                  setDraftFeature(null);
                  setEditMode(false);
                }}
                onDraftChange={(feature) => setDraftFeature({ ...feature, geometry: { ...feature.geometry, coordinates: [closeRing(rings(feature)[0]), ...rings(feature).slice(1)] } })}
              />
            ) : (
              <LegendPreview
                collection={collection}
                focusedLegendItemId={focusedLegendItemId}
                checkedLegendItemIds={checkedLegendItemIds}
                reviewStatuses={legendReviewStatuses}
                onFocusItem={focusLegendItem}
                onToggleItem={toggleLegendItem}
                onReviewItem={(itemId, status) => setLegendReviewStatuses((current) => ({ ...current, [itemId]: status }))}
                onActivateVectorDefinitions={() => setDetailTabRequest(`vector:legend:${Date.now()}`)}
              />
            )}
          </div>
          {layout.resultsHidden ? null : (
            <div
              role="separator"
              aria-label="Resize results panel"
              aria-orientation="horizontal"
              data-testid="resize-results"
              className="relative z-10 h-px bg-slate-300"
              onPointerDown={beginResultsResize}
            >
              <div className="absolute -top-2 -bottom-2 left-0 right-0 cursor-row-resize" />
            </div>
          )}
          {layout.resultsHidden ? null : (
            <DefinitionExplorer
              collection={collection}
              visibleFeatures={visibleFeatures}
              selected={selected}
              remapConfig={remapConfig}
              requestedTab={detailTabRequest}
              focusedLegendItemId={focusedLegendItemId}
              checkedLegendItemIds={checkedLegendItemIds}
              legendReviewStatuses={legendReviewStatuses}
            />
          )}
        </div>
        {layout.reviewHidden ? null : (
          <div
            role="separator"
            aria-label="Resize review panel"
            aria-orientation="vertical"
            data-testid="resize-review"
            className="relative z-10 w-px bg-slate-300"
            onPointerDown={beginReviewResize}
          >
            <div className="absolute -left-2 -right-2 bottom-0 top-0 cursor-col-resize" />
          </div>
        )}
        {layout.reviewHidden ? null : <div className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)]">
          <div className="border-b border-slate-200 bg-white px-3 py-2 text-xs">
            <div className="font-semibold text-slate-900">{sourceLabel}</div>
            <div className="mt-1 grid grid-cols-2 gap-1 text-[11px] text-slate-600">
              <span>CRS: {collection?.coordinate_system ?? "PDF_PAGE_POINTS_Y_DOWN_NO_CRS"}</span>
              <span>Status: {collection?.classification_status ?? "regression_sample"}</span>
              <span>Features: {features.length}</span>
              <span>Algorithm: {collection?.selected_algorithm ?? "fixture"}</span>
              <span>Source: {collection?.source_type ?? "local"}</span>
              <span>Run: {collection?.run_id ?? "n/a"}</span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-2 text-[11px] text-slate-600">
              <button type="button" onClick={() => setLayout((current) => ({ ...current, reviewHidden: !current.reviewHidden }))} className="rounded border border-slate-300 px-2 py-1">
                {layout.reviewHidden ? "Show review" : "Hide review"}
              </button>
              <button type="button" onClick={() => setLayout((current) => ({ ...current, resultsHidden: !current.resultsHidden }))} className="rounded border border-slate-300 px-2 py-1">
                {layout.resultsHidden ? "Show results" : "Hide results"}
              </button>
              <button type="button" onClick={() => setLayout(DEFAULT_LAYOUT)} className="rounded border border-slate-300 px-2 py-1">
                Reset layout
              </button>
            </div>
          </div>
          <ManualReviewPanel
            selected={selected}
            draftFeature={draftFeature}
            editMode={editMode}
            lastEdit={lastEdit}
            annotations={annotations}
            onBeginEdit={beginEdit}
            onCancelEdit={() => {
              setDraftFeature(null);
              setEditMode(false);
            }}
            onSaveEdit={saveEdit}
            onAddVertex={addVertex}
            onDeleteVertex={deleteVertex}
            onSaveAnnotation={createAnnotation}
          />
        </div>}
        {layout.reviewHidden || layout.resultsHidden ? (
          <div className="fixed bottom-3 right-3 z-10 flex gap-2 rounded-md border border-slate-300 bg-white p-2 text-xs shadow">
            {layout.reviewHidden ? <button type="button" onClick={() => setLayout((current) => ({ ...current, reviewHidden: false }))} className="rounded border border-slate-300 px-2 py-1">Show review</button> : null}
            {layout.resultsHidden ? <button type="button" onClick={() => setLayout((current) => ({ ...current, resultsHidden: false }))} className="rounded border border-slate-300 px-2 py-1">Show results</button> : null}
            <button type="button" onClick={() => setLayout(DEFAULT_LAYOUT)} className="rounded border border-slate-300 px-2 py-1">Reset layout</button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
