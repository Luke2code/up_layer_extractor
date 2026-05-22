import { useEffect, useRef, useState } from "react";

import type { GeoFeature, Ring } from "../types";
import { centerOfRing, CLASS_COLORS, pathForRing, pathForRings, rings, updateOuterRing } from "../lib/geo";

export type MapColorMode = "source" | "classification" | "review" | "artifact" | "neutral";

interface PageSize {
  width: number;
  height: number;
}

interface MapPreviewProps {
  features: GeoFeature[];
  selected: GeoFeature | null;
  draftFeature: GeoFeature | null;
  editMode: boolean;
  pageSize: PageSize;
  showPlanImage: boolean;
  planImageUrl?: string | null;
  experimentCandidates?: GeoFeature[];
  colorMode: MapColorMode;
  overlay: number;
  toggles: {
    plan: boolean;
    polygons: boolean;
    validation: boolean;
    selectedBorder: boolean;
    selectedLabel: boolean;
    textLabel: boolean;
    fidLabel: boolean;
    classLabel: boolean;
  };
  onSelect: (feature: GeoFeature | null) => void;
  onDraftChange: (feature: GeoFeature) => void;
}

interface ViewState {
  scale: number;
  tx: number;
  ty: number;
}

type FitMode = "page" | "width" | "polygon" | "custom";

const MIN_ZOOM = 0.25;
const V8_1_MAX_ZOOM = 16;
const MAX_ZOOM = V8_1_MAX_ZOOM * 100;
const ZOOM_STEPS = [
  { label: "25%", scale: 0.25 },
  { label: "50%", scale: 0.5 },
  { label: "100%", scale: 1 },
  { label: "200%", scale: 2 },
  { label: "400%", scale: 4 },
  { label: "800%", scale: 8 },
  { label: "1600%", scale: 16 },
  { label: "3200%", scale: 32 },
  { label: "6400%", scale: 64 },
  { label: "Max", scale: MAX_ZOOM }
];

function svgPoint(svg: SVGSVGElement, clientX: number, clientY: number, pageSize: PageSize) {
  const rect = svg.getBoundingClientRect();
  return {
    x: ((clientX - rect.left) / rect.width) * pageSize.width,
    y: ((clientY - rect.top) / rect.height) * pageSize.height
  };
}

function selectedKey(feature: GeoFeature | null) {
  return feature ? String(feature.id ?? feature.properties.FID) : "";
}

function bboxForFeature(feature: GeoFeature | null) {
  if (!feature) return null;
  const points = rings(feature).flat();
  if (!points.length) return null;
  const xs = points.map((point) => point[0]);
  const ys = points.map((point) => point[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)] as [number, number, number, number];
}

function centeredViewForBBox(bbox: [number, number, number, number], pageSize: PageSize, padding = 1.25): ViewState {
  const width = Math.max(1, bbox[2] - bbox[0]);
  const height = Math.max(1, bbox[3] - bbox[1]);
  const scale = Math.max(1, Math.min(MAX_ZOOM, Math.min(pageSize.width / (width * padding), pageSize.height / (height * padding))));
  const cx = (bbox[0] + bbox[2]) / 2;
  const cy = (bbox[1] + bbox[3]) / 2;
  return {
    scale,
    tx: pageSize.width / 2 - cx * scale,
    ty: pageSize.height / 2 - cy * scale
  };
}

function fitButtonClass(active: boolean) {
  return `px-2 py-1 text-[11px] ${active ? "bg-slate-900 text-white" : "bg-white text-slate-700 hover:bg-slate-100"}`;
}

function selectedLabel(feature: GeoFeature | null) {
  if (!feature) return [];
  const props = feature.properties;
  const primary = props.proposed_CLASS && props.proposed_CLASS !== "UNMAPPED"
    ? String(props.proposed_CLASS)
    : String(props.CLASS ?? "UNMAPPED");
  const secondary = props.text_id ? String(props.text_id) : props.proposed_LAYER_CLASS ? String(props.proposed_LAYER_CLASS) : String(props.LAYER_CLASS ?? "");
  return [`FID ${String(props.FID ?? feature.id ?? "?")}`, secondary ? `${primary} / ${secondary}` : primary];
}

function featureColor(feature: GeoFeature, colorMode: MapColorMode) {
  const props = feature.properties;
  const source = String(props.display_fill_hex ?? props.source_fill_hex ?? props.source_style_hex ?? "#9ca3af");
  if (colorMode === "source") return source;
  if (colorMode === "neutral") return "#9ca3af";
  if (colorMode === "classification") {
    return CLASS_COLORS[String(props.proposed_CLASS ?? props.CLASS ?? "")] ?? source;
  }
  if (colorMode === "review") {
    const status = String(props.review_status ?? props.classification_status ?? "");
    if (status.includes("approved")) return "#2f9e44";
    if (status.includes("rejected")) return "#c92a2a";
    if (status.includes("artifact")) return "#f08c00";
    return "#748ffc";
  }
  const flags = Array.isArray(props.artifact_flags) ? props.artifact_flags.map(String).join(" ") : "";
  if (flags.includes("void")) return "#e8590c";
  if (flags.includes("needle") || flags.includes("sliver") || flags.includes("thin_corridor")) return "#d6336c";
  if (flags.includes("artifact")) return "#f08c00";
  return "#94d82d";
}

function insertVertex(ring: Ring, point: [number, number]): Ring {
  if (ring.length < 2) return ring;
  let bestIndex = 1;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (let index = 0; index < ring.length - 1; index += 1) {
    const a = ring[index];
    const b = ring[index + 1];
    const mid: [number, number] = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    const distance = Math.hypot(point[0] - mid[0], point[1] - mid[1]);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index + 1;
    }
  }
  return [...ring.slice(0, bestIndex), point, ...ring.slice(bestIndex)];
}

export function MapPreview({ features, selected, draftFeature, editMode, pageSize, showPlanImage, planImageUrl, experimentCandidates = [], colorMode, overlay, toggles, onSelect, onDraftChange }: MapPreviewProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [view, setView] = useState<ViewState>({ scale: 1, tx: 0, ty: 0 });
  const [fitMode, setFitMode] = useState<FitMode>("page");
  const [panStart, setPanStart] = useState<{ x: number; y: number; tx: number; ty: number } | null>(null);
  const [dragVertex, setDragVertex] = useState<number | null>(null);
  const activeSelected = draftFeature ?? selected;
  const selectedId = selectedKey(selected);
  const showAnyLabel = toggles.textLabel || toggles.fidLabel || toggles.classLabel;
  const selectedBBox = bboxForFeature(activeSelected);
  const canFitPolygon = Boolean(selectedBBox && selectedBBox[2] > selectedBBox[0] && selectedBBox[3] > selectedBBox[1]);
  const rawSelectedFlags = activeSelected?.properties.artifact_flags;
  const selectedFlags = Array.isArray(rawSelectedFlags) ? rawSelectedFlags.map(String) : [];
  const selectedArtifactState = selectedFlags.some((flag) => flag.includes("artifact") || flag.includes("void") || flag.includes("sliver") || flag.includes("thin") || flag.includes("needle"));
  const selectedLabelRows = selectedLabel(activeSelected);
  const selectedLabelFontSize = Math.max(2, 7 / Math.sqrt(Math.max(view.scale, 1)));
  const selectedLabelStrokeWidth = Math.max(0.55, 1.8 / Math.sqrt(Math.max(view.scale, 1)));

  useEffect(() => {
    setView({ scale: 1, tx: 0, ty: 0 });
    setFitMode("page");
  }, [pageSize.width, pageSize.height]);

  function pointInWorld(event: React.MouseEvent<SVGSVGElement> | React.PointerEvent<SVGCircleElement>) {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const p = svgPoint(svg, event.clientX, event.clientY, pageSize);
    return { x: (p.x - view.tx) / view.scale, y: (p.y - view.ty) / view.scale };
  }

  function onWheel(event: React.WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    const svg = svgRef.current;
    if (!svg) return;
    const p = svgPoint(svg, event.clientX, event.clientY, pageSize);
    const nextScale = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, view.scale * (event.deltaY < 0 ? 1.22 : 1 / 1.22)));
    const wx = (p.x - view.tx) / view.scale;
    const wy = (p.y - view.ty) / view.scale;
    setFitMode("custom");
    setView({ scale: nextScale, tx: p.x - wx * nextScale, ty: p.y - wy * nextScale });
  }

  function fitPage() {
    setFitMode("page");
    setView({ scale: 1, tx: 0, ty: 0 });
  }

  function fitWidth() {
    const rect = svgRef.current?.getBoundingClientRect();
    const containerAspect = rect ? rect.width / Math.max(rect.height, 1) : pageSize.width / pageSize.height;
    const pageAspect = pageSize.width / Math.max(pageSize.height, 1);
    const scale = Math.max(1, Math.min(4, containerAspect / Math.max(pageAspect, 0.001)));
    setFitMode("width");
    setView({
      scale,
      tx: pageSize.width / 2 - (pageSize.width / 2) * scale,
      ty: pageSize.height / 2 - (pageSize.height / 2) * scale
    });
  }

  function fitPolygon() {
    if (!selectedBBox) return;
    setFitMode("polygon");
    setView(centeredViewForBBox(selectedBBox, pageSize));
  }

  function setZoomScale(nextScale: number) {
    const scale = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, nextScale));
    setFitMode("custom");
    setView({
      scale,
      tx: pageSize.width / 2 - ((pageSize.width / 2 - view.tx) / view.scale) * scale,
      ty: pageSize.height / 2 - ((pageSize.height / 2 - view.ty) / view.scale) * scale
    });
  }

  function onMouseMove(event: React.MouseEvent<SVGSVGElement>) {
    if (dragVertex !== null && draftFeature) {
      const world = pointInWorld(event);
      const ring = rings(draftFeature)[0];
      const nextRing = ring.map((point, index) => (index === dragVertex || (dragVertex === 0 && index === ring.length - 1) ? [world.x, world.y] as [number, number] : point));
      onDraftChange(updateOuterRing(draftFeature, nextRing));
      return;
    }
    if (!panStart) return;
    const svg = svgRef.current;
    if (!svg) return;
    const p = svgPoint(svg, event.clientX, event.clientY, pageSize);
    setFitMode("custom");
    setView({ scale: view.scale, tx: panStart.tx + (p.x - panStart.x), ty: panStart.ty + (p.y - panStart.y) });
  }

  function resetPan() {
    setPanStart(null);
    setDragVertex(null);
  }

  function addPointToDraft(event: React.MouseEvent<SVGPathElement>, feature: GeoFeature) {
    if (!editMode || selectedKey(feature) !== selectedId || !draftFeature) return;
    event.stopPropagation();
    const world = pointInWorld(event as unknown as React.MouseEvent<SVGSVGElement>);
    const ring = rings(draftFeature)[0];
    onDraftChange(updateOuterRing(draftFeature, insertVertex(ring, [world.x, world.y])));
  }

  const selectedRing = activeSelected ? rings(activeSelected)[0] : null;
  const selectedCenter = selectedRing ? centerOfRing(selectedRing) : null;

  return (
    <div className="relative h-full min-h-0 overflow-hidden bg-white">
      <div data-testid="viewport-fit-control" className="absolute left-1/2 top-2 z-10 flex max-w-[calc(100%-1rem)] -translate-x-1/2 items-center gap-1 overflow-x-auto bg-white/95 p-1 shadow-sm">
        <div className="inline-flex border border-slate-300">
          <button type="button" data-testid="fit-page" onClick={fitPage} className={fitButtonClass(fitMode === "page")}>Fit Page</button>
          <button type="button" data-testid="fit-width" onClick={fitWidth} className={fitButtonClass(fitMode === "width")}>Fit Width</button>
          <button type="button" data-testid="fit-polygon" disabled={!canFitPolygon} onClick={fitPolygon} className={`${fitButtonClass(fitMode === "polygon")} disabled:cursor-not-allowed disabled:opacity-40`}>Fit Polygon</button>
        </div>
        <div data-testid="zoom-step-control" className="inline-flex border border-slate-300">
          {ZOOM_STEPS.map((step) => (
            <button
              key={step.label}
              type="button"
              data-testid={`zoom-step-${step.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
              onClick={() => setZoomScale(step.scale)}
              className={`px-1.5 py-1 text-[10px] ${Math.abs(view.scale - step.scale) / Math.max(step.scale, 1) < 0.04 ? "bg-slate-900 text-white" : "bg-white text-slate-700 hover:bg-slate-100"}`}
            >
              {step.label}
            </button>
          ))}
        </div>
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${pageSize.width} ${pageSize.height}`}
        className="block h-full min-h-0 w-full bg-white"
        preserveAspectRatio="xMidYMid meet"
        onWheel={onWheel}
        onMouseDown={(event) => {
          const svg = svgRef.current;
          if (!svg) return;
          const p = svgPoint(svg, event.clientX, event.clientY, pageSize);
          setFitMode("custom");
          setPanStart({ x: p.x, y: p.y, tx: view.tx, ty: view.ty });
        }}
        onMouseMove={onMouseMove}
        onMouseUp={resetPan}
        onMouseLeave={resetPan}
        onClick={() => onSelect(null)}
        role="img"
        aria-label="UP layer map preview"
      >
        <defs>
          <pattern id="navrhHatch" width="8" height="8" patternUnits="userSpaceOnUse">
            <path d="M -2 8 L 8 -2 M 3 10 L 10 3" stroke="#111" strokeWidth="0.8" opacity=".45" />
          </pattern>
          <pattern id="stavDot" width="9" height="9" patternUnits="userSpaceOnUse">
            <circle cx="4.5" cy="4.5" r="1" fill="#111" opacity=".20" />
          </pattern>
        </defs>
        <g transform={`translate(${view.tx} ${view.ty}) scale(${view.scale})`}>
          {showPlanImage ? (
            <>
              <image href={planImageUrl ?? "/kvetnice_plan.jpg"} x="0" y="0" width={pageSize.width} height={pageSize.height} preserveAspectRatio="none" opacity="0.98" data-testid="plan-image" />
              <rect x="0" y="0" width={pageSize.width} height={pageSize.height} fill="#fff" opacity={overlay} pointerEvents="none" />
            </>
          ) : null}
          {toggles.validation
            ? features.map((feature) => {
                const featureRings = rings(feature);
                if (!featureRings.length) return null;
                const path = pathForRings(featureRings);
                return (
                  <g key={`validation-${feature.id ?? feature.properties.FID}`} pointerEvents="none">
                    <path d={path} fill={feature.properties.TYPE === "NAVRH" ? "#ffd84d" : "#4dabf7"} fillOpacity={feature.properties.TYPE === "NAVRH" ? 0.32 : 0.22} fillRule="evenodd" />
                    <path d={path} fill={feature.properties.TYPE === "NAVRH" ? "url(#navrhHatch)" : "url(#stavDot)"} fillRule="evenodd" />
                  </g>
                );
              })
            : null}
          {toggles.polygons
            ? features.map((feature) => {
                const props = feature.properties;
                const isSelected = selectedKey(feature) === selectedId;
                const renderedFeature = isSelected && draftFeature ? draftFeature : feature;
                const featureRings = rings(renderedFeature);
                if (!featureRings.length) return null;
                const candidateColor = featureColor(feature, colorMode);
                return (
                  <path
                    key={`poly-${feature.id ?? props.FID}`}
                    data-testid={`feature-${props.FID ?? feature.id}`}
                    d={pathForRings(featureRings)}
                    fill={candidateColor}
                    fillOpacity={props.LAYER === "ZMEN" ? 0.12 : props.confidence === "review_required" ? 0.56 : 0.42}
                    fillRule="evenodd"
                    stroke={String(props.display_stroke_hex ?? props.source_stroke_hex ?? (props.LAYER === "ZMEN" ? "#111" : "#222"))}
                    strokeWidth={props.LAYER === "ZMEN" ? 1.5 : 0.75}
                    strokeDasharray={props.LAYER === "ZMEN" ? "8 5" : undefined}
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelect(feature);
                    }}
                    onDoubleClick={(event) => addPointToDraft(event, feature)}
                    className="cursor-pointer outline-none focus:ring-2 focus:ring-accent"
                  />
                );
              })
            : null}
          {experimentCandidates.map((feature) => {
            const featureRings = rings(feature);
            if (!featureRings.length) return null;
            return (
              <g key={`experiment-${feature.id ?? feature.properties.candidate_id ?? "candidate"}`} pointerEvents="none" data-testid="experiment-candidate-split">
                <path d={pathForRings(featureRings)} fill="#06b6d4" fillOpacity="0.08" stroke="#0891b2" strokeWidth={3} strokeDasharray="10 5" fillRule="evenodd" />
                <path d={pathForRings(featureRings)} fill="none" stroke="#facc15" strokeWidth={1.2} strokeDasharray="2 7" strokeLinecap="round" />
              </g>
            );
          })}
          {toggles.selectedBorder && activeSelected
            ? rings(activeSelected).map((ring, index) => (
                <path
                  key={`selected-${index}`}
                  d={pathForRing(ring)}
                  fill="none"
                  stroke={selectedArtifactState ? (index === 0 ? "#f59e0b" : "#dc2626") : "#ffd400"}
                  strokeWidth={selectedArtifactState ? (index === 0 ? 2.8 : 2.2) : 2.55}
                  strokeDasharray={selectedArtifactState ? (index === 0 ? "5 4" : "1 5") : "1 6"}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  pointerEvents="none"
                />
              ))
            : null}
          {editMode && activeSelected && selectedRing
            ? selectedRing.slice(0, -1).map((point, index) => (
                <circle
                  key={`vertex-${index}`}
                  cx={point[0]}
                  cy={point[1]}
                  r={4.2}
                  fill="#fff"
                  stroke="#5F7600"
                  strokeWidth={1.4}
                  className="cursor-move"
                  onPointerDown={(event) => {
                    event.stopPropagation();
                    setDragVertex(index);
                  }}
                />
              ))
            : null}
          {showAnyLabel
            ? features.map((feature) => {
                const props = feature.properties;
                const ring = rings(feature)[0];
                if (!ring) return null;
                const center = centerOfRing(ring);
                return (
                  <g key={`label-${feature.id ?? props.FID}`} pointerEvents="none" fontFamily="Arial" fontSize="9" textAnchor="middle">
                    {toggles.textLabel && props.text_id ? <text x={center.x} y={center.y - 8} fill="#111" stroke="#fff" strokeWidth="2" paintOrder="stroke">{props.text_id}</text> : null}
                    {toggles.classLabel ? <text x={center.x} y={center.y + 2} fill="#111" stroke="#fff" strokeWidth="2" paintOrder="stroke">{props.CLASS}</text> : null}
                    {toggles.fidLabel ? <text x={center.x} y={center.y + 13} fill="#334155" stroke="#fff" strokeWidth="2" paintOrder="stroke">{props.FID}</text> : null}
                  </g>
                );
              })
            : null}
          {toggles.selectedLabel && selectedCenter && selectedLabelRows.length ? (
            <g transform={`translate(${selectedCenter.x} ${selectedCenter.y})`} pointerEvents="none" data-testid="selected-polygon-label">
              <text y={-selectedLabelFontSize * 0.55} textAnchor="middle" fontSize={selectedLabelFontSize} fontWeight="700" fill="#111" stroke="#fff" strokeWidth={selectedLabelStrokeWidth} paintOrder="stroke">
                {selectedLabelRows[0]}
              </text>
              <text y={selectedLabelFontSize * 0.85} textAnchor="middle" fontSize={selectedLabelFontSize} fontWeight="700" fill="#111" stroke="#fff" strokeWidth={selectedLabelStrokeWidth} paintOrder="stroke">
                {selectedLabelRows[1]}
              </text>
            </g>
          ) : null}
        </g>
      </svg>
    </div>
  );
}
