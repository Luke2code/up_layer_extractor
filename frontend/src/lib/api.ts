import type { AnnotationRecord, DefinitionCandidate, FeatureCollection, LegendLabelCorrectionRecord, ManualEditRecord, RemapResult } from "../types";

export async function loadSample(): Promise<FeatureCollection> {
  const response = await fetch("/api/sample/kvetnice");
  if (!response.ok) throw new Error(`sample load failed: HTTP ${response.status}`);
  return response.json() as Promise<FeatureCollection>;
}

export async function loadJsonUrl(url: string): Promise<FeatureCollection> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<FeatureCollection>;
}

export async function extractPdfUrl(url: string): Promise<FeatureCollection> {
  const response = await fetch("/api/extract", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url })
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<FeatureCollection>;
}

export async function uploadPdf(file: File): Promise<FeatureCollection> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/extract_upload", { method: "POST", body });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<FeatureCollection>;
}

export async function uploadSource(file: File): Promise<FeatureCollection> {
  return uploadPdf(file);
}

export async function exportRecords(collection: FeatureCollection, kind: string): Promise<{ filename: string; text: string }> {
  const response = await fetch(`/api/exports/${kind}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feature_collection: collection })
  });
  if (!response.ok) throw new Error(await response.text());
  const disposition = response.headers.get("content-disposition") ?? "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? `${collection.collection_id ?? "collection"}_${kind}.txt`;
  return { filename, text: await response.text() };
}

export async function generateDefinitionCandidates(collection: FeatureCollection): Promise<{ vector_definitions: DefinitionCandidate[]; text_definitions: DefinitionCandidate[] }> {
  const response = await fetch("/api/definitions/candidates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feature_collection: collection })
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{ vector_definitions: DefinitionCandidate[]; text_definitions: DefinitionCandidate[] }>;
}

export async function approveDefinition(candidateId: string, kind: "vector" | "text"): Promise<DefinitionCandidate> {
  const response = await fetch("/api/definitions/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate_id: candidateId, kind })
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<DefinitionCandidate>;
}

export async function saveManualEdit(payload: Record<string, unknown>): Promise<ManualEditRecord> {
  const response = await fetch("/api/manual/edits", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ManualEditRecord>;
}

export async function saveAnnotation(payload: Record<string, unknown>): Promise<AnnotationRecord> {
  const response = await fetch("/api/manual/annotations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<AnnotationRecord>;
}

export async function saveManualLegendCrop(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const response = await fetch("/api/manual/legend_crop", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<Record<string, unknown>>;
}

export async function saveManualLegendLabel(payload: Record<string, unknown>): Promise<LegendLabelCorrectionRecord> {
  const response = await fetch("/api/manual/legend_label", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<LegendLabelCorrectionRecord>;
}

export async function previewRemap(payload: Record<string, unknown>): Promise<RemapResult> {
  const response = await fetch("/api/remap/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<RemapResult>;
}
