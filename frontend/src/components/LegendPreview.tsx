import { AlertTriangle, Check, Crosshair, Edit3, Square, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type WheelEvent as ReactWheelEvent } from "react";

import { saveManualLegendCrop, saveManualLegendLabel } from "../lib/api";
import type { FeatureCollection, LegendCrop, LegendItem, LegendLabelCorrectionRecord, LegendSymbol, VectorSpec } from "../types";

interface LegendPreviewProps {
  collection: FeatureCollection | null;
  focusedLegendItemId: string | null;
  checkedLegendItemIds: Set<string>;
  reviewStatuses: Record<string, string>;
  onFocusItem: (itemId: string) => void;
  onToggleItem: (itemId: string) => void;
  onReviewItem: (itemId: string, status: string) => void;
  onActivateVectorDefinitions: () => void;
}

type OverlayOptions = {
  rows: boolean;
  symbols: boolean;
  selectedOnly: boolean;
  labels: boolean;
};

type FitMode = "page" | "width" | "custom";
type ImageBBox = [number, number, number, number];

const EXPECTED_SYMBOLS = ["1 STAV/STABIL", "2 NAVRH"];

function pct(value: number, total: number | null | undefined) {
  return total ? `${(value / total) * 100}%` : "0%";
}

function boxStyle(bbox: number[] | null | undefined, width: number | null | undefined, height: number | null | undefined) {
  if (!bbox) return {};
  return {
    left: pct(bbox[0], width),
    top: pct(bbox[1], height),
    width: pct(Math.max(1, bbox[2] - bbox[0]), width),
    height: pct(Math.max(1, bbox[3] - bbox[1]), height)
  };
}

function normalizedImageBBox(bbox: ImageBBox | null): ImageBBox | null {
  if (!bbox) return null;
  return [Math.min(bbox[0], bbox[2]), Math.min(bbox[1], bbox[3]), Math.max(bbox[0], bbox[2]), Math.max(bbox[1], bbox[3])];
}

function imagePoint(event: ReactPointerEvent<HTMLDivElement>, width: number | null | undefined, height: number | null | undefined): [number, number] {
  const rect = event.currentTarget.getBoundingClientRect();
  const imageWidth = Math.max(Number(width ?? rect.width), 1);
  const imageHeight = Math.max(Number(height ?? rect.height), 1);
  return [
    Math.max(0, Math.min(imageWidth, ((event.clientX - rect.left) / Math.max(rect.width, 1)) * imageWidth)),
    Math.max(0, Math.min(imageHeight, ((event.clientY - rect.top) / Math.max(rect.height, 1)) * imageHeight))
  ];
}

function pageBBoxFromImageBBox(crop: LegendCrop | undefined, bbox: ImageBBox | null): number[] | null {
  const normalized = normalizedImageBBox(bbox);
  if (!crop || !normalized) return null;
  const transform = (crop.page_to_image_transform ?? {}) as Record<string, unknown>;
  const scaleX = Number(transform.page_to_image_scale_x ?? crop.page_to_image_scale_x);
  const scaleY = Number(transform.page_to_image_scale_y ?? crop.page_to_image_scale_y);
  const offsetX = Number(transform.page_to_image_offset_x ?? crop.page_to_image_offset_x ?? 0);
  const offsetY = Number(transform.page_to_image_offset_y ?? crop.page_to_image_offset_y ?? 0);
  if (Number.isFinite(scaleX) && Number.isFinite(scaleY) && scaleX > 0 && scaleY > 0) {
    return [
      (normalized[0] - offsetX) / scaleX,
      (normalized[1] - offsetY) / scaleY,
      (normalized[2] - offsetX) / scaleX,
      (normalized[3] - offsetY) / scaleY
    ].map((value) => Math.round(value * 1000) / 1000);
  }
  const cropBBox = crop.crop_bbox_page_pt;
  const imageWidth = Number(crop.image_width_px ?? 0);
  const imageHeight = Number(crop.image_height_px ?? 0);
  if (cropBBox && imageWidth > 0 && imageHeight > 0) {
    return [
      cropBBox[0] + (normalized[0] / imageWidth) * (cropBBox[2] - cropBBox[0]),
      cropBBox[1] + (normalized[1] / imageHeight) * (cropBBox[3] - cropBBox[1]),
      cropBBox[0] + (normalized[2] / imageWidth) * (cropBBox[2] - cropBBox[0]),
      cropBBox[1] + (normalized[3] / imageHeight) * (cropBBox[3] - cropBBox[1])
    ].map((value) => Math.round(value * 1000) / 1000);
  }
  return null;
}

function fitButtonClass(active: boolean) {
  return `px-2 py-1 text-[11px] ${active ? "bg-slate-900 text-white" : "bg-white text-slate-700 hover:bg-slate-100"}`;
}

function swatchStyle(symbol: LegendSymbol) {
  return {
    background: symbol.symbol_status === "missing_expected_symbol_requires_review" ? "transparent" : `${symbol.symbol_fill_hex ?? "transparent"}66`,
    borderColor: symbol.symbol_stroke_hex ?? "#475569"
  };
}

function symbolLabel(symbol: LegendSymbol) {
  if (symbol.symbol_role === "stav_stabil") return "1 STAV/STABIL";
  if (symbol.symbol_role === "navrh") return "2 NAVRH";
  return `${symbol.symbol_order ?? "?"} ${symbol.symbol_role ?? "symbol"}`;
}

function reviewState(item: LegendItem, reviewStatuses: Record<string, string>) {
  return reviewStatuses[item.legend_item_id] ?? item.review_status ?? "unreviewed";
}

function itemExportEligible(item: LegendItem, checked: boolean, review: string) {
  return checked && review === "approved" && (item.missing_expected_symbol_count ?? 0) === 0;
}

export function LegendPreview({
  collection,
  focusedLegendItemId,
  checkedLegendItemIds,
  reviewStatuses,
  onFocusItem,
  onToggleItem,
  onReviewItem,
  onActivateVectorDefinitions
}: LegendPreviewProps) {
  const [manualBBox, setManualBBox] = useState("90,1180,710,2175");
  const [manualNote, setManualNote] = useState("");
  const [manualStatus, setManualStatus] = useState("");
  const [cropIndex, setCropIndex] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [fitMode, setFitMode] = useState<FitMode>("page");
  const [manualCropMode, setManualCropMode] = useState(false);
  const [manualDraft, setManualDraft] = useState<ImageBBox | null>(null);
  const [manualDragStart, setManualDragStart] = useState<[number, number] | null>(null);
  const [overlays, setOverlays] = useState<OverlayOptions>({ rows: true, symbols: false, selectedOnly: false, labels: false });
  const [manualLabels, setManualLabels] = useState<Record<string, LegendLabelCorrectionRecord>>({});
  const [editingLabelFor, setEditingLabelFor] = useState<string | null>(null);
  const [labelDraft, setLabelDraft] = useState("");
  const cropScrollerRef = useRef<HTMLDivElement>(null);

  const crops = (collection?.legend_crops ?? []) as LegendCrop[];
  const usableCrops = crops.filter((row) => row.image_artifact_url || row.image_artifact_path_or_url);
  const crop = usableCrops[cropIndex] ?? usableCrops[0];
  const items = ((collection?.legend_items ?? []) as LegendItem[]).filter((item) => item.legend_crop_id === crop?.legend_crop_id);
  const symbols = ((collection?.legend_symbols ?? []) as LegendSymbol[]).filter((symbol) => symbol.legend_crop_id === crop?.legend_crop_id);
  const vectorDefinitions = (collection?.vector_definitions ?? collection?.vector_specs ?? []) as VectorSpec[];

  const symbolsByItem = useMemo(() => {
    const grouped = new Map<string, LegendSymbol[]>();
    for (const symbol of symbols) {
      if (!symbol.legend_item_id) continue;
      grouped.set(symbol.legend_item_id, [...(grouped.get(symbol.legend_item_id) ?? []), symbol]);
    }
    for (const group of grouped.values()) group.sort((left, right) => (left.symbol_order ?? 0) - (right.symbol_order ?? 0));
    return grouped;
  }, [symbols]);

  const vectorDefsByItem = useMemo(() => {
    const grouped = new Map<string, VectorSpec[]>();
    for (const row of vectorDefinitions) {
      const itemId = row.legend_item_id;
      if (!itemId) continue;
      grouped.set(String(itemId), [...(grouped.get(String(itemId)) ?? []), row]);
    }
    return grouped;
  }, [vectorDefinitions]);

  const focused = items.find((item) => item.legend_item_id === focusedLegendItemId) ?? items[0] ?? null;
  const focusedSymbols = focused ? symbolsByItem.get(focused.legend_item_id) ?? [] : [];
  const focusedVectorDefs = focused ? vectorDefsByItem.get(focused.legend_item_id) ?? [] : [];
  const focusedReview = focused ? reviewState(focused, reviewStatuses) : "unreviewed";
  const focusedChecked = focused ? checkedLegendItemIds.has(focused.legend_item_id) : false;
  const focusedExportEligible = focused ? itemExportEligible(focused, focusedChecked, focusedReview) : false;
  const imageSrc = crop?.image_artifact_url ?? crop?.image_artifact_path_or_url ?? "";
  const imageWidth = crop?.image_width_px ?? null;
  const imageHeight = crop?.image_height_px ?? null;
  const cropSource = String(crop?.legend_crop_source ?? collection?.legend_crop_source ?? (crop ? "auto" : "unavailable"));
  const manualBox = normalizedImageBBox(manualDraft);
  const columnIndexes = [...new Set(items.map((item) => Number(item.legend_column_index ?? 0)))].sort((a, b) => a - b);

  function cropLabel(row: LegendCrop, index: number) {
    const source = String(row.legend_crop_source ?? row.anchor_type ?? "");
    const count = items.length;
    if (source.includes("manual")) return `Manual crop · ${count} rows`;
    if (source.includes("target")) return `Target rows · ${count} rows`;
    if (index === 0) return `Main legend · ${count} rows`;
    return `Debug crop ${index + 1}`;
  }

  function displayLabel(item: LegendItem | null) {
    if (!item) return "";
    return manualLabels[item.legend_item_id]?.corrected_label ?? item.label_text_display ?? item.label_text_decoded ?? (item.label_text_status === "ok" ? item.label_text_raw : null) ?? "label unreadable - review";
  }

  useEffect(() => {
    if (!focused) return;
    const node = cropScrollerRef.current?.querySelector(`[data-testid="legend-item-${focused.code_text}"]`);
    node?.scrollIntoView({ block: "center", inline: "nearest" });
  }, [focused?.legend_item_id, focused?.code_text, zoom, fitMode]);

  useEffect(() => {
    setFitMode("page");
    setZoom(1);
    setCropIndex(0);
    setManualCropMode(false);
    setManualDraft(null);
    setManualDragStart(null);
  }, [collection?.collection_id]);

  function focusItem(item: LegendItem) {
    onFocusItem(item.legend_item_id);
    onActivateVectorDefinitions();
  }

  function moveFocus(current: LegendItem, delta: number) {
    const index = items.findIndex((item) => item.legend_item_id === current.legend_item_id);
    const next = items[Math.max(0, Math.min(items.length - 1, index + delta))];
    if (next) {
      focusItem(next);
      window.setTimeout(() => {
        const node = document.querySelector(`[data-testid="legend-list-row-${next.code_text ?? next.legend_item_id}"]`) as HTMLElement | null;
        node?.focus();
      }, 0);
    }
  }

  function setOverlay(key: keyof OverlayOptions, value: boolean) {
    setOverlays((current) => ({ ...current, [key]: value }));
  }

  function onCropWheel(event: ReactWheelEvent<HTMLDivElement>) {
    if (!imageSrc) return;
    const node = cropScrollerRef.current;
    if (!node) return;
    const rect = node.getBoundingClientRect();
    const beforeX = event.clientX - rect.left + node.scrollLeft;
    const beforeY = event.clientY - rect.top + node.scrollTop;
    const nextZoom = Math.max(0.35, Math.min(4, zoom * (event.deltaY < 0 ? 1.12 : 1 / 1.12)));
    const ratio = nextZoom / zoom;
    setFitMode("custom");
    setZoom(nextZoom);
    requestAnimationFrame(() => {
      node.scrollLeft = beforeX * ratio - (event.clientX - rect.left);
      node.scrollTop = beforeY * ratio - (event.clientY - rect.top);
    });
  }

  function fitPage() {
    setFitMode("page");
    setZoom(1);
  }

  function fitWidth() {
    setFitMode("width");
    setZoom(1);
  }

  function beginManualCrop() {
    setManualCropMode((current) => !current);
    setManualStatus("drag a rectangle on the legend viewport, then save crop");
  }

  function startManualDraft(event: ReactPointerEvent<HTMLDivElement>) {
    if (!manualCropMode) return;
    event.preventDefault();
    event.stopPropagation();
    const point = imagePoint(event, imageWidth, imageHeight);
    setManualDragStart(point);
    setManualDraft([point[0], point[1], point[0], point[1]]);
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function moveManualDraft(event: ReactPointerEvent<HTMLDivElement>) {
    if (!manualCropMode || !manualDragStart) return;
    event.preventDefault();
    const point = imagePoint(event, imageWidth, imageHeight);
    setManualDraft([manualDragStart[0], manualDragStart[1], point[0], point[1]]);
  }

  function finishManualDraft(event: ReactPointerEvent<HTMLDivElement>) {
    if (!manualCropMode || !manualDragStart) return;
    event.preventDefault();
    const point = imagePoint(event, imageWidth, imageHeight);
    const nextDraft: ImageBBox = [manualDragStart[0], manualDragStart[1], point[0], point[1]];
    setManualDraft(nextDraft);
    setManualDragStart(null);
    const pageBox = pageBBoxFromImageBBox(crop, nextDraft);
    if (pageBox) {
      setManualBBox(pageBox.join(","));
      setManualStatus("manual crop rectangle staged");
    }
    event.currentTarget.releasePointerCapture(event.pointerId);
  }

  async function saveLabelCorrection(item: LegendItem) {
    const corrected = labelDraft.trim();
    if (!corrected) return;
    setManualStatus("saving label correction");
    try {
      const record = await saveManualLegendLabel({
        collection_id: collection?.collection_id,
        legend_item_id: item.legend_item_id,
        legend_row_id: item.legend_row_id,
        legend_crop_id: item.legend_crop_id,
        code_text: item.code_text,
        original_raw_label: item.label_text_raw,
        corrected_label: corrected,
        reason: "operator corrected unreadable legend label",
        created_by: "operator-ui"
      });
      setManualLabels((current) => ({ ...current, [item.legend_item_id]: record }));
      setEditingLabelFor(null);
      setLabelDraft("");
      setManualStatus("label correction saved as manual review record");
    } catch (error) {
      setManualStatus(`label correction failed: ${(error as Error).message}`);
    }
  }

  async function saveManualCrop() {
    setManualStatus("saving manual crop");
    try {
      const bbox = pageBBoxFromImageBBox(crop, manualDraft) ?? manualBBox.split(",").map((part) => Number(part.trim()));
      const result = await saveManualLegendCrop({
        collection_id: collection?.collection_id,
        source_filename: collection?.source_filename,
        bbox_page_pt: bbox,
        legend_crop_source: "manual",
        manual_crop_image_bbox_px: normalizedImageBBox(manualDraft),
        derived_from_legend_crop_id: crop?.legend_crop_id,
        note: manualNote,
        timestamp: new Date().toISOString()
      });
      setManualStatus(String(result.status ?? "saved"));
      setManualCropMode(false);
    } catch (error) {
      setManualStatus(`manual crop failed: ${(error as Error).message}`);
    }
  }

  if (!collection) {
    return <div className="grid min-h-0 place-items-center bg-white text-sm text-slate-500">No source loaded</div>;
  }

  return (
    <div className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] bg-white" data-testid="legend-workbench">
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-3 py-2 text-xs">
        <div>
          <div className="text-sm font-semibold text-slate-900">Legend Workbench</div>
          <div className="text-[11px] text-slate-500">Focus, checked, review, and export eligibility are separate states.</div>
        </div>
        {usableCrops.length ? (
          <div className="flex flex-wrap items-center gap-1">
            {usableCrops.map((row, index) => (
              <button key={row.legend_crop_id ?? index} type="button" onClick={() => { setCropIndex(index); setFitMode("page"); setZoom(1); setManualDraft(null); }} className={`border px-2 py-1 ${cropIndex === index ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white"}`}>
                {cropLabel(row, index)}
              </button>
            ))}
            {crops.length > usableCrops.length ? <span className="text-[11px] text-slate-500">Debug crops hidden: {crops.length - usableCrops.length}</span> : null}
          </div>
        ) : <span className="text-[11px] text-slate-500">Legend unavailable</span>}
      </div>

      {imageSrc ? (
        <div className="grid min-h-0 gap-0 lg:grid-cols-[minmax(0,1fr)_420px]">
          <div className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] border-r border-slate-200">
            <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-3 py-2 text-xs">
              <span className="bg-slate-100 px-2 py-1 text-[11px] text-slate-700">Source: {cropSource}</span>
              <button type="button" data-testid="manual-crop-action" onClick={beginManualCrop} className={`inline-flex items-center gap-1 border px-2 py-1 ${manualCropMode ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white"}`}>
                <Crosshair className="h-3.5 w-3.5" />Manual crop
              </button>
              <span data-testid="legend-zoom-state" className="text-[11px] text-slate-500">{fitMode === "page" ? "Fit Page" : fitMode === "width" ? "Fit Width" : `${Math.round(zoom * 100)}%`}</span>
              {[
                ["rows", "Rows"],
                ["symbols", "Symbols"],
                ["selectedOnly", "Selected only"],
                ["labels", "Show labels"]
              ].map(([key, label]) => (
                <label key={key} className="inline-flex items-center gap-1 border border-slate-300 bg-white px-2 py-1">
                  <input type="checkbox" checked={overlays[key as keyof OverlayOptions]} onChange={(event) => setOverlay(key as keyof OverlayOptions, event.target.checked)} />
                  {label}
                </label>
              ))}
            </div>

            <div className="relative min-h-0">
              <div data-testid="legend-fit-control" className="absolute left-1/2 top-2 z-20 inline-flex -translate-x-1/2 border border-slate-300 bg-white shadow-sm">
                <button type="button" data-testid="legend-fit-page" onClick={fitPage} className={fitButtonClass(fitMode === "page")}>Fit Page</button>
                <button type="button" data-testid="legend-fit-width" onClick={fitWidth} className={fitButtonClass(fitMode === "width")}>Fit Width</button>
              </div>
              <div ref={cropScrollerRef} onWheel={onCropWheel} className="thin-scrollbar h-full min-h-0 overflow-auto overscroll-contain bg-slate-100 p-0" data-testid="legend-crop-viewer">
              <div
                className={`${fitMode === "width" ? "relative w-full" : "relative inline-block"} ${manualCropMode ? "cursor-crosshair" : ""} bg-white`}
                style={
                  fitMode === "custom"
                    ? { width: `${Math.round(zoom * 100)}%`, minWidth: `${Math.round(zoom * 100)}%` }
                    : fitMode === "page"
                      ? { maxWidth: "100%", maxHeight: "100%" }
                      : undefined
                }
                onPointerDown={startManualDraft}
                onPointerMove={moveManualDraft}
                onPointerUp={finishManualDraft}
                onPointerCancel={() => setManualDragStart(null)}
              >
                <img src={imageSrc} alt="Legend crop" className={`${fitMode === "page" ? "block max-h-full max-w-full select-none" : "block w-full select-none"}`} draggable={false} />
                {manualBox ? (
                  <div
                    data-testid="manual-crop-rectangle"
                    className="pointer-events-none absolute border-2 border-amber-500 bg-amber-300/20"
                    style={boxStyle(manualBox, imageWidth, imageHeight)}
                  />
                ) : null}
                {overlays.rows
                  ? items.map((item) => {
                      const isFocused = item.legend_item_id === focused?.legend_item_id;
                      const shouldShow = !overlays.selectedOnly || isFocused;
                      if (!shouldShow) return null;
                      const checked = checkedLegendItemIds.has(item.legend_item_id);
                      const review = reviewState(item, reviewStatuses);
                      return (
                        <div
                          key={item.legend_item_id}
                          role="button"
                          tabIndex={0}
                          aria-label={`Legend item ${item.code_text ?? item.legend_item_id}`}
                          aria-pressed={isFocused}
                          data-testid={`legend-item-${item.code_text ?? item.legend_item_id}`}
                          onClick={() => focusItem(item)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") {
                              focusItem(item);
                            } else if (event.key === " ") {
                              event.preventDefault();
                              onToggleItem(item.legend_item_id);
                            } else if (event.key === "ArrowDown" || event.key === "ArrowRight") {
                              event.preventDefault();
                              moveFocus(item, 1);
                            } else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
                              event.preventDefault();
                              moveFocus(item, -1);
                            }
                          }}
                          className={`absolute rounded-[2px] border bg-transparent transition ${manualCropMode ? "pointer-events-none" : ""} ${
                            isFocused ? "border-[#5F7600] ring-2 ring-[#5F7600]/25" : "border-slate-400/60 hover:border-slate-700"
                          }`}
                          style={boxStyle(item.row_bbox_image_px, imageWidth, imageHeight)}
                        >
                          <span className={`absolute left-0 top-1 h-3 w-1.5 -translate-x-2 rounded-full ${review === "approved" ? "bg-emerald-600" : review === "rejected" ? "bg-red-600" : "bg-slate-500"}`} />
                          {checked ? <Check className="absolute left-1 top-1 h-3 w-3 rounded bg-white text-[#5F7600]" aria-hidden /> : null}
                          {overlays.labels ? <span className="absolute left-5 top-1 rounded bg-white/90 px-1 text-[10px] font-semibold text-slate-900">{item.code_text}</span> : null}
                        </div>
                      );
                    })
                  : null}
                {overlays.symbols
                  ? symbols.map((symbol) => {
                      const isSelectedSymbol = symbol.legend_item_id === focused?.legend_item_id;
                      if (overlays.selectedOnly && !isSelectedSymbol) return null;
                      if (!symbol.symbol_bbox_image_px) return null;
                      return (
                        <span
                          key={symbol.legend_symbol_id}
                          data-testid="legend-symbol-overlay"
                          className={`pointer-events-none absolute border bg-transparent text-[9px] font-semibold ${
                            isSelectedSymbol ? "border-[#5F7600]" : "border-slate-500/60"
                          }`}
                          style={{ ...boxStyle(symbol.symbol_bbox_image_px, imageWidth, imageHeight), ...swatchStyle(symbol) }}
                          title={`${symbol.symbol_role ?? "symbol"} ${symbol.symbol_status ?? ""}`}
                        >
                          <span className="absolute -left-1 -top-1 grid h-3.5 w-3.5 place-items-center rounded-full bg-white/95 text-[9px] text-slate-900 shadow-sm">
                            {symbol.symbol_order}
                          </span>
                        </span>
                      );
                    })
                  : null}
              </div>
              </div>
            </div>
          </div>

          <div className="thin-scrollbar min-h-0 overflow-auto bg-white">
            {focused ? (
              <div className="border-b border-slate-200 p-3" data-testid="legend-selected-inspector">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-[11px] font-medium uppercase text-slate-500">Selected legend item</div>
                    <div className="text-xl font-semibold text-slate-950">{focused.code_text}</div>
                    <div className="mt-1 text-sm font-medium text-slate-700" data-testid="legend-selected-label">{displayLabel(focused)}</div>
                    <div className="mt-0.5 text-[11px] text-slate-500">
                      label: {String(focused.label_text_status ?? "unknown")} · source: {String(focused.label_text_source ?? "unknown")}
                    </div>
                  </div>
                  <span className="border border-slate-300 px-2 py-1 text-xs">Column {Number(focused.legend_column_index ?? 0) + 1}</span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <span className="border border-slate-200 bg-slate-50 p-2">Review<br /><b>{focusedReview}</b></span>
                  <span className="border border-slate-200 bg-slate-50 p-2">Confidence<br /><b>{String(focused.confidence ?? "n/a")}</b></span>
                  <span className="border border-slate-200 bg-slate-50 p-2">Checked<br /><b>{focusedChecked ? "yes" : "no"}</b></span>
                  <span className="border border-slate-200 bg-slate-50 p-2">Export eligible<br /><b>{focusedExportEligible ? "yes" : "no"}</b></span>
                </div>
                <div className="mt-3 grid gap-2 text-xs">
                  <div className="font-semibold text-slate-800">Symbols</div>
                  {EXPECTED_SYMBOLS.map((expected) => {
                    const order = expected.startsWith("1") ? 1 : 2;
                    const symbol = focusedSymbols.find((row) => row.symbol_order === order);
                    const missing = !symbol || symbol.symbol_status === "missing_expected_symbol_requires_review";
                    return (
                      <div key={expected} className="flex items-center justify-between gap-2 border border-slate-200 bg-white px-2 py-1.5">
                        <span className="font-medium">{expected}</span>
                        {missing ? (
                          <span className="inline-flex items-center gap-1 text-amber-700"><AlertTriangle className="h-3.5 w-3.5" />missing requires review</span>
                        ) : (
                          <span className="inline-flex items-center gap-1">
                            <span className="h-3 w-5 border" style={swatchStyle(symbol)} />
                            {symbol.symbol_status ?? "detected"}
                          </span>
                        )}
                      </div>
                    );
                  })}
                  {focusedSymbols.filter((symbol) => symbol.symbol_role === "ignored_extra" || symbol.symbol_status === "ignored_extra").map((symbol) => (
                    <div key={symbol.legend_symbol_id} className="border border-slate-200 bg-slate-50 px-2 py-1.5 text-slate-600">
                      Ignored extra: {symbolLabel(symbol)}
                    </div>
                  ))}
                </div>
                <div className="mt-3 text-xs text-slate-600">
                  Reason: {String(focused.status_reason ?? "legend row detected from target code anchors and symbol swatches; approval is still required")}
                </div>
                <div className="mt-3 border border-slate-200 bg-slate-50 p-2 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <div className="font-semibold">Label review</div>
                      <div className="text-slate-600">Raw: {String(focused.label_text_raw ?? "empty")}</div>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingLabelFor(focused.legend_item_id);
                        setLabelDraft(displayLabel(focused));
                      }}
                      className="inline-flex items-center gap-1 border border-slate-300 bg-white px-2 py-1"
                    >
                      <Edit3 className="h-3.5 w-3.5" />Edit label
                    </button>
                  </div>
                  {editingLabelFor === focused.legend_item_id ? (
                    <div className="mt-2 grid grid-cols-[minmax(0,1fr)_auto] gap-2">
                      <input value={labelDraft} onChange={(event) => setLabelDraft(event.target.value)} className="border border-slate-300 px-2 py-1" aria-label="Corrected legend label" />
                      <button type="button" onClick={() => void saveLabelCorrection(focused)} className="border border-slate-300 bg-white px-2 py-1">Save</button>
                    </div>
                  ) : null}
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  <button type="button" onClick={() => focusItem(focused)} className="inline-flex items-center gap-1 border border-slate-300 bg-white px-2 py-1"><Crosshair className="h-3.5 w-3.5" />Focus row</button>
                  <button type="button" aria-label={`Toggle ${focused.code_text}`} onClick={() => onToggleItem(focused.legend_item_id)} className="inline-flex items-center gap-1 border border-slate-300 bg-white px-2 py-1">
                    {focusedChecked ? <Check className="h-3.5 w-3.5" /> : <Square className="h-3.5 w-3.5" />}
                    {focusedChecked ? "Uncheck" : "Check"}
                  </button>
                  <button type="button" onClick={() => onReviewItem(focused.legend_item_id, "approved")} className="border border-slate-300 bg-white px-2 py-1">Approve</button>
                  <button type="button" onClick={() => onReviewItem(focused.legend_item_id, "rejected")} className="inline-flex items-center gap-1 border border-slate-300 bg-white px-2 py-1"><X className="h-3.5 w-3.5" />Reject</button>
                  <button type="button" onClick={() => onReviewItem(focused.legend_item_id, "requires_review")} className="border border-slate-300 bg-white px-2 py-1">Requires review</button>
                  <button type="button" onClick={() => setManualStatus("manual mapping correction requested")} className="border border-slate-300 bg-white px-2 py-1">Create/fix manual mapping</button>
                </div>
                <div className="mt-3 border border-slate-200 bg-slate-50 p-2 text-xs">
                  <div className="font-semibold">Vector definition mapping</div>
                  <div>Expected rows: {EXPECTED_SYMBOLS.join(", ")}</div>
                  <div>Found rows: {focusedVectorDefs.length} / Missing: {Math.max(0, 2 - focusedVectorDefs.length)}</div>
                  <div>Ignored extras: {focused.ignored_extra_symbol_count ?? 0}</div>
                  <div>{focusedVectorDefs.map((row) => `${row.symbol_order} ${row.symbol_role} ${row.class_type}/${row.class_type_id}`).join("; ") || "No normal vector definition rows"}</div>
                </div>
              </div>
            ) : null}

            <div className="border-b border-slate-200 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="text-sm font-semibold text-slate-900">Legend item list</div>
                <div className="text-[11px] text-slate-500">{items.length} items · {columnIndexes.length || 1} column{(columnIndexes.length || 1) === 1 ? "" : "s"}</div>
              </div>
              <div className="thin-scrollbar max-h-[32rem] overflow-auto border border-slate-200">
                <table className="w-full border-collapse text-left text-[11px]">
                  <thead className="sticky top-0 bg-slate-100 text-[10px] uppercase text-slate-600">
                    <tr>
                      <th className="px-2 py-2">Check</th>
                      <th className="px-2 py-2">Code</th>
                      <th className="px-2 py-2">Short label</th>
                      <th className="px-2 py-2">Symbols</th>
                      <th className="px-2 py-2">Review</th>
                      <th className="px-2 py-2">Defs</th>
                      <th className="px-2 py-2">Conf.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => {
                      const itemSymbols = symbolsByItem.get(item.legend_item_id) ?? [];
                      const foundOrders = new Set(itemSymbols.filter((symbol) => symbol.symbol_status !== "missing_expected_symbol_requires_review").map((symbol) => symbol.symbol_order));
                      const missing = item.missing_expected_symbol_count ?? 0;
                      const checked = checkedLegendItemIds.has(item.legend_item_id);
                      const review = reviewState(item, reviewStatuses);
                      const isFocused = item.legend_item_id === focused?.legend_item_id;
                      return (
                        <tr
                          key={item.legend_item_id}
                          data-testid={`legend-list-row-${item.code_text ?? item.legend_item_id}`}
                          tabIndex={0}
                          className={`cursor-pointer border-b border-slate-100 ${isFocused ? "bg-[#eef3dc]" : "hover:bg-slate-50"}`}
                          onClick={() => focusItem(item)}
                          onKeyDown={(event) => {
                            if (event.key === "ArrowDown") {
                              event.preventDefault();
                              moveFocus(item, 1);
                            } else if (event.key === "ArrowUp") {
                              event.preventDefault();
                              moveFocus(item, -1);
                            } else if (event.key === "Enter") {
                              event.preventDefault();
                              focusItem(item);
                            } else if (event.key === " ") {
                              event.preventDefault();
                              onToggleItem(item.legend_item_id);
                            }
                          }}
                        >
                          <td className="px-2 py-1">
                            <button
                              type="button"
                              aria-label={`Toggle ${item.code_text}`}
                              onClick={(event) => {
                                event.stopPropagation();
                                onToggleItem(item.legend_item_id);
                              }}
                              className="grid h-5 w-5 place-items-center border border-slate-300 bg-white"
                            >
                              {checked ? <Check className="h-3.5 w-3.5 text-[#5F7600]" /> : <Square className="h-3.5 w-3.5 text-slate-500" />}
                            </button>
                          </td>
                          <td className="px-2 py-1 font-semibold text-slate-900">{item.code_text}</td>
                          <td className="max-w-[10rem] truncate px-2 py-1" title={`raw: ${String(item.label_text_raw ?? "empty")}`}>{displayLabel(item)}</td>
                          <td className="px-2 py-1">{[1, 2].map((order) => foundOrders.has(order) ? order : null).filter(Boolean).join(", ") || "none"}{missing ? " / missing" : ""}</td>
                          <td className="px-2 py-1">{review}</td>
                          <td className="px-2 py-1">{item.normal_vector_def_row_count ?? 0}</td>
                          <td className="px-2 py-1">{String(item.confidence ?? "n/a")}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="grid gap-2 p-3 text-xs">
              <div className="text-sm font-semibold">Manual legend crop</div>
              <div className="grid gap-2">
                <input value={manualBBox} onChange={(event) => setManualBBox(event.target.value)} className="border border-slate-300 px-2 py-1" aria-label="Manual legend crop bbox" />
                <input value={manualNote} onChange={(event) => setManualNote(event.target.value)} className="border border-slate-300 px-2 py-1" placeholder="note / reason" />
                <button type="button" onClick={() => void saveManualCrop()} className="border border-slate-300 px-2 py-1">Save crop</button>
              </div>
              {manualStatus ? <div className="text-slate-600">{manualStatus}</div> : null}
            </div>
          </div>
        </div>
      ) : (
        <div className="grid place-items-center p-6 text-sm text-slate-600" data-testid="legend-unavailable">
          <div className="max-w-xl border border-slate-200 bg-slate-50 p-4">
            <div className="font-semibold text-slate-900">Legend unavailable</div>
            <div className="mt-1">
              {String(collection.legend_unavailable_reason ?? "Current source has no usable legend crop artifact. Use manual legend crop for PDF sources.")}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
