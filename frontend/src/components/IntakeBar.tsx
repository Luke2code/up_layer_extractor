import { FileUp, Link, Play, RotateCcw } from "lucide-react";
import { useRef, useState } from "react";

import type { FeatureCollection } from "../types";
import { extractPdfUrl, loadSample, uploadSource } from "../lib/api";
import { normalizeFeatureCollection } from "../lib/geo";

const BABICE_URL =
  "https://www.babice.eu/e_download.php?file=data/editor/327cs_1.pdf&original=Babice_UZ_Z12.pdf";

interface IntakeBarProps {
  collection: FeatureCollection | null;
  sourceLabel: string;
  onLoad: (collection: FeatureCollection, label: string) => void;
  onResetLayout?: () => void;
}

type RequestState = "idle" | "running" | "completed" | "failed";

function sourceDisplayName(label: string, collection: FeatureCollection | null) {
  if (collection?.source_filename) return String(collection.source_filename);
  if (!label) return "no source";
  try {
    const parsed = new URL(label);
    const pathName = decodeURIComponent(parsed.pathname.split("/").filter(Boolean).pop() ?? parsed.hostname);
    return pathName || parsed.hostname;
  } catch {
    return label.split(/[\\/]/).pop() || label;
  }
}

function sourceBadge(collection: FeatureCollection | null): "VECTOR" | "RASTER" | "OTHER" {
  const sourceType = String(collection?.source_type ?? collection?.source_detection?.source_type ?? "").toLowerCase();
  const detection = collection?.source_detection;
  if (detection?.has_vector_drawings || sourceType.includes("vector") || sourceType.includes("mixed_pdf")) return "VECTOR";
  if (detection?.is_probably_scanned || sourceType.includes("raster") || (detection?.has_images && !detection?.has_vector_drawings)) return "RASTER";
  return "OTHER";
}

function sourceSummary(collection: FeatureCollection) {
  return `${collection.source_type ?? "source"} · ${collection.primary_extraction_mode ?? "loaded"} · raw ${collection.raw_fragment_count ?? collection.features.length} · merged ${collection.feature_count ?? collection.features.length} · warnings 0 · errors ${collection.error_count ?? 0}`;
}

export function IntakeBar({ collection, sourceLabel, onLoad, onResetLayout }: IntakeBarProps) {
  const [url, setUrl] = useState("");
  const [lastUrl, setLastUrl] = useState("");
  const [status, setStatus] = useState("sample loaded");
  const [requestState, setRequestState] = useState<RequestState>("idle");
  const fileRef = useRef<HTMLInputElement>(null);
  const busy = requestState === "running";
  const displayName = sourceDisplayName(sourceLabel, collection);
  const badge = sourceBadge(collection);

  async function runLoadSample() {
    if (busy) return;
    setRequestState("running");
    setStatus("loading bundled sample");
    try {
      const sample = normalizeFeatureCollection(await loadSample());
      onLoad(sample, "Kvetnice bundled sample");
      setStatus(`${sample.features.length} sample features`);
      setRequestState("completed");
    } catch (error) {
      setStatus(`sample load failed: ${(error as Error).message}`);
      setRequestState("failed");
    }
  }

  async function runLoadAndExtract() {
    if (!url.trim() || busy) return;
    setRequestState("running");
    setStatus("loading and extracting via backend");
    try {
      const collection = normalizeFeatureCollection(await extractPdfUrl(url.trim()));
      onLoad(collection, url.trim());
      setLastUrl(url.trim());
      setStatus(sourceSummary(collection));
      setRequestState("completed");
    } catch (error) {
      setStatus(`source load failed: ${(error as Error).message}`);
      setRequestState("failed");
    }
  }

  async function retryLast() {
    if (!lastUrl || busy) return;
    setUrl(lastUrl);
    setRequestState("running");
    setStatus("retrying last source");
    try {
      const collection = normalizeFeatureCollection(await extractPdfUrl(lastUrl));
      onLoad(collection, lastUrl);
      setStatus(sourceSummary(collection));
      setRequestState("completed");
    } catch (error) {
      setStatus(`retry failed: ${(error as Error).message}`);
      setRequestState("failed");
    }
  }

  function exportLogs() {
    const blob = new Blob([JSON.stringify({ status, lastUrl, timestamp: new Date().toISOString() }, null, 2)], { type: "application/json" });
    const anchor = document.createElement("a");
    anchor.href = URL.createObjectURL(blob);
    anchor.download = "up-layer-ui-log.json";
    anchor.click();
    URL.revokeObjectURL(anchor.href);
  }

  async function runFile(file: File | undefined) {
    if (!file || busy) return;
    setRequestState("running");
    try {
      if (file.name.toLowerCase().endsWith(".pdf") || file.type.includes("pdf")) {
        setStatus("extracting upload via backend");
        const collection = normalizeFeatureCollection(await uploadSource(file));
        onLoad(collection, file.name);
        setStatus(sourceSummary(collection));
        setRequestState("completed");
        return;
      }
      const collection = normalizeFeatureCollection(await uploadSource(file));
      onLoad(collection, file.name);
      setStatus(sourceSummary(collection));
      setRequestState("completed");
    } catch (error) {
      setStatus(`file load failed: ${(error as Error).message}`);
      setRequestState("failed");
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-white px-3 py-2">
      <div className="flex min-w-0 items-center gap-2 text-sm font-semibold text-slate-900">
        <span className="truncate" title={`UP Layer Extractor · ${displayName}`}>UP Layer Extractor · {displayName}</span>
        <span className="bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600">{badge}</span>
      </div>
      <div className="flex min-w-[18rem] flex-1 items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1">
        <Link className="h-4 w-4 text-slate-500" aria-hidden />
        <input
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !busy) void runLoadAndExtract();
          }}
          className="min-w-0 flex-1 bg-transparent text-xs outline-none"
          placeholder="PDF URL, GeoJSON URL, UP page URL, or upload file"
          type="url"
          disabled={busy}
        />
      </div>
      <button type="button" disabled={busy || !url.trim()} onClick={runLoadAndExtract} className="inline-flex items-center gap-1 rounded-md border border-accent bg-accent px-2 py-1 text-xs font-medium text-white hover:bg-[#536700] disabled:cursor-not-allowed disabled:opacity-50">
        <Play className="h-3.5 w-3.5" aria-hidden />
        Load + Extract
      </button>
      <input ref={fileRef} className="hidden" type="file" accept=".geojson,.json,.pdf,application/json,application/pdf" disabled={busy} onChange={(event) => void runFile(event.target.files?.[0])} />
      <button type="button" disabled={busy} onClick={() => fileRef.current?.click()} className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
        <FileUp className="h-3.5 w-3.5" aria-hidden />
        Upload
      </button>
      <details className="relative">
        <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs hover:bg-slate-50">
          <RotateCcw className="h-3.5 w-3.5" aria-hidden />
          Debug
        </summary>
        <div className="absolute right-0 z-20 mt-1 grid min-w-36 gap-1 rounded-md border border-slate-200 bg-white p-1 shadow-lg">
          <button type="button" disabled={busy} onClick={() => void runLoadSample()} className="rounded px-2 py-1 text-left text-xs hover:bg-slate-50 disabled:opacity-50">Sample</button>
          <button type="button" disabled={busy || !lastUrl} onClick={() => void retryLast()} className="rounded px-2 py-1 text-left text-xs hover:bg-slate-50 disabled:opacity-50">Retry</button>
          <button type="button" onClick={exportLogs} className="rounded px-2 py-1 text-left text-xs hover:bg-slate-50">Export logs</button>
          <button
            type="button"
            onClick={() => {
              onResetLayout?.();
              setStatus("layout reset");
            }}
            className="rounded px-2 py-1 text-left text-xs hover:bg-slate-50"
          >
            Reset layout
          </button>
          <button
            type="button"
            onClick={() => {
              setUrl(BABICE_URL);
              setStatus("Babice Z12 URL inserted");
            }}
            className="rounded px-2 py-1 text-left text-xs hover:bg-slate-50"
          >
            Babice Z12
          </button>
        </div>
      </details>
      <span data-testid="backend-status" className={`inline-flex items-center gap-1 px-2 py-1 text-[11px] ${
        requestState === "running" ? "bg-amber-50 text-amber-800" : requestState === "failed" ? "bg-red-50 text-red-700" : requestState === "completed" ? "bg-emerald-50 text-emerald-700" : "bg-slate-50 text-slate-600"
      }`}>
        {requestState === "running" ? <span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" /> : null}
        {requestState}
      </span>
      <span className="max-w-[32rem] truncate bg-slate-50 px-2 py-1 text-[11px] text-slate-600" title={status}>{status}</span>
    </div>
  );
}
