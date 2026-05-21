import { RotateCcw } from "lucide-react";

import { SegmentedControl } from "./SegmentedControl";
import type { Filters, GeoFeature } from "../types";
import { filterOptions } from "../lib/geo";
import type { MapColorMode } from "./MapPreview";

interface ToolbarProps {
  features: GeoFeature[];
  visibleCount: number;
  filters: Filters;
  overlay: number;
  toggles: {
    plan: boolean;
    polygons: boolean;
    validation: boolean;
    selectedBorder: boolean;
    textLabel: boolean;
    fidLabel: boolean;
    classLabel: boolean;
  };
  planAvailable: boolean;
  planSource: string;
  colorMode: MapColorMode;
  onFilterChange: (key: keyof Filters, value: string) => void;
  onOverlayChange: (value: number) => void;
  onColorModeChange: (value: MapColorMode) => void;
  onToggleChange: (key: keyof ToolbarProps["toggles"], value: boolean) => void;
  onResetView: () => void;
}

export function Toolbar({ features, visibleCount, filters, overlay, toggles, planAvailable, planSource, colorMode, onFilterChange, onOverlayChange, onColorModeChange, onToggleChange, onResetView }: ToolbarProps) {
  const options = filterOptions(features, filters);
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-slate-200 bg-white px-3 py-2">
      <span className="bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-700">
        {visibleCount} / {features.length} features
      </span>
      <SegmentedControl label="LAYER" options={options.layers} value={filters.LAYER} onChange={(value) => onFilterChange("LAYER", value)} />
      <SegmentedControl label="CLASS" options={options.classes} value={filters.CLASS} onChange={(value) => onFilterChange("CLASS", value)} />
      <SegmentedControl label="TYPE" options={options.types} value={filters.TYPE} onChange={(value) => onFilterChange("TYPE", value)} />
      <SegmentedControl label="IS_CLOSED" options={options.closed} value={filters.IS_CLOSED} onChange={(value) => onFilterChange("IS_CLOSED", value)} />
      <label className={`flex items-center gap-1 bg-slate-50 px-2 py-1 text-[11px] ${planAvailable ? "" : "text-slate-400"}`}>
        <input type="checkbox" checked={toggles.plan && planAvailable} disabled={!planAvailable} onChange={(event) => onToggleChange("plan", event.target.checked)} />
        Plan {planAvailable ? "" : "unavailable"}
      </label>
      <span className="bg-slate-50 px-2 py-1 text-[11px] text-slate-600">Plan source: {planSource}</span>
      <label className="flex items-center gap-1 bg-slate-50 px-2 py-1 text-[11px]">
        Color
        <select
          data-testid="color-mode-selector"
          value={colorMode}
          onChange={(event) => onColorModeChange(event.target.value as MapColorMode)}
          className="bg-white text-[11px] outline-none"
        >
          <option value="source">Source colors</option>
          <option value="classification">Classification colors</option>
          <option value="review">Review status colors</option>
          <option value="artifact">Artifact colors</option>
          <option value="neutral">Neutral grey</option>
        </select>
      </label>
      <label className="flex items-center gap-1 bg-slate-50 px-2 py-1 text-[11px]">
        Overlay
        <input className="w-24 accent-[#5F7600]" type="range" min={0} max={0.85} step={0.05} value={overlay} onChange={(event) => onOverlayChange(Number(event.target.value))} />
        <span>{Math.round(overlay * 100)}%</span>
      </label>
      {[
        ["polygons", "Polygons"],
        ["validation", "Raster validation"],
        ["selectedBorder", "Selected border"],
        ["textLabel", "text_id"],
        ["fidLabel", "FID"],
        ["classLabel", "CLASS"]
      ].map(([key, label]) => (
        <label key={key} className="flex items-center gap-1 bg-slate-50 px-2 py-1 text-[11px]">
          <input type="checkbox" checked={toggles[key as keyof typeof toggles]} onChange={(event) => onToggleChange(key as keyof typeof toggles, event.target.checked)} />
          {label}
        </label>
      ))}
      <button type="button" onClick={onResetView} className="ml-auto inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs hover:bg-slate-50">
        <RotateCcw className="h-3.5 w-3.5" aria-hidden />
        Reset view
      </button>
    </div>
  );
}
