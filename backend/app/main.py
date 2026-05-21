from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .algorithms import (
    ALGORITHM_REGISTRY,
    diagnostic_failure_collection,
    diagnostics_from_drawings,
    extract_url_to_feature_collection,
    extract_vector_candidates,
)
from .pipeline import enrich_geojson_collection, export_collection
from .remapping import RemapConfig, remap_class
from .schemas import (
    AnnotationRequest,
    DefinitionApprovalRequest,
    ExtractRequest,
    FeatureCollectionRequest,
    HealthResponse,
    ManualEditRequest,
    RemapOverrideRequest,
    RemapPreviewRequest,
)
from .store import InMemoryStore


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "vector_layer_class_type_remap.json"
SAMPLE_PATH = REPO_ROOT / "frontend" / "public" / "kvetnice_up_layers_unified_pagecoords.geojson"

remap_config = RemapConfig.load(CONFIG_PATH)
store = InMemoryStore(remap_config=remap_config)

app = FastAPI(title="UP Layer Extractor", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/artifacts", StaticFiles(directory=REPO_ROOT / "docs"), name="artifacts")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True, service="up-layer-extractor", version="1.0.0")


@app.get("/api/registry")
def registry() -> dict[str, Any]:
    return {"algorithms": [descriptor.model_dump() for descriptor in ALGORITHM_REGISTRY.values()]}


@app.get("/api/sample/kvetnice")
def sample_kvetnice() -> dict[str, Any]:
    return enrich_geojson_collection(
        json.loads(SAMPLE_PATH.read_text(encoding="utf-8")),
        source_filename=SAMPLE_PATH.name,
        source_url="sample:kvetnice",
        source_origin="bundled_sample",
    )


@app.post("/api/extract")
def extract(req: ExtractRequest) -> dict[str, Any]:
    try:
        return extract_url_to_feature_collection(str(req.url))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/extract_upload")
async def extract_upload(file: UploadFile) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(415, "Upload must include a filename")
    with tempfile.TemporaryDirectory() as tmp:
        payload = await file.read()
        lower = file.filename.lower()
        if lower.endswith((".json", ".geojson")) or "json" in (file.content_type or ""):
            try:
                collection = json.loads(payload.decode("utf-8"))
            except Exception as exc:
                raise HTTPException(422, f"Uploaded JSON could not be parsed: {exc}") from exc
            if collection.get("type") != "FeatureCollection":
                raise HTTPException(415, "Uploaded JSON is not a GeoJSON FeatureCollection")
            return enrich_geojson_collection(
                collection,
                source_filename=file.filename,
                source_url=f"upload:{file.filename}",
                source_origin="geojson_upload",
            )
        if not lower.endswith(".pdf") and "pdf" not in (file.content_type or ""):
            raise HTTPException(415, "Upload must be a PDF or GeoJSON FeatureCollection")
        pdf = Path(tmp) / Path(file.filename).name
        pdf.write_bytes(payload)
        return extract_vector_candidates(pdf, source_url=f"upload:{file.filename}")


@app.post("/api/definitions/candidates")
def definition_candidates(req: FeatureCollectionRequest) -> dict[str, Any]:
    return store.generate_definition_candidates(req.feature_collection)


@app.get("/api/definitions/candidates/sample")
def sample_definition_candidates() -> dict[str, Any]:
    return store.generate_definition_candidates(sample_kvetnice())


@app.post("/api/definitions/approve")
def approve_definition(req: DefinitionApprovalRequest) -> dict[str, Any]:
    try:
        return store.approve_definition(req.candidate_id, req.kind, req.approved_by)
    except KeyError as exc:
        raise HTTPException(404, f"candidate not found: {req.candidate_id}") from exc


@app.post("/api/manual/edits")
def create_manual_edit(req: ManualEditRequest) -> dict[str, Any]:
    try:
        return store.create_manual_edit(req.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/manual/annotations")
def create_annotation(req: AnnotationRequest) -> dict[str, Any]:
    return store.create_annotation(req.model_dump())


@app.post("/api/manual/legend_crop")
def create_manual_legend_crop(payload: dict[str, Any]) -> dict[str, Any]:
    bbox = payload.get("bbox_page_pt") or payload.get("crop_bbox_page_pt")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise HTTPException(422, "bbox_page_pt must contain four page-coordinate numbers")
    try:
        bbox = [float(value) for value in bbox]
    except Exception as exc:
        raise HTTPException(422, "bbox_page_pt values must be numeric") from exc
    if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        raise HTTPException(422, "bbox_page_pt must have positive width and height")
    return {
        "manual_crop_id": f"manual-legend-crop-{len(store.state().get('manual_edits', [])) + 1:04d}",
        "status": "saved_for_review",
        "bbox_page_pt": bbox,
        "legend_crop_source": "manual",
        "manual_crop_bbox_page_pt": bbox,
        "manual_crop_image_bbox_px": payload.get("manual_crop_image_bbox_px"),
        "derived_from_legend_crop_id": payload.get("derived_from_legend_crop_id"),
        "collection_id": payload.get("collection_id"),
        "source_filename": payload.get("source_filename"),
        "note": payload.get("note"),
        "source_page": payload.get("page_number", 1),
        "timestamp": payload.get("timestamp"),
        "review_status": "requires_review",
        "artifact_path": None,
        "reason": "manual legend crop request recorded as operator metadata; raw extraction output remains immutable and rerender is pending durable run storage",
    }


@app.post("/api/manual/legend_label")
def create_manual_legend_label(payload: dict[str, Any]) -> dict[str, Any]:
    corrected = str(payload.get("corrected_label") or "").strip()
    if not corrected:
        raise HTTPException(422, "corrected_label is required")
    return store.create_legend_label_correction(payload)


@app.post("/api/remap/preview")
def remap_preview(req: RemapPreviewRequest) -> dict[str, Any]:
    result = remap_class(
        layer=req.layer,
        class_name=req.class_name,
        raw_type_text=req.type_text,
        ref=req.ref,
        config=remap_config,
    )
    return result.model_dump()


@app.post("/api/remap/override")
def create_remap_override(req: RemapOverrideRequest) -> dict[str, Any]:
    if (req.override_layer.startswith("CUST") or req.override_class.startswith("X")) and not req.note:
        raise HTTPException(422, "note is required for custom remap overrides")
    return store.create_remap_override(req.model_dump())


@app.post("/api/exports/{kind}")
def export_records(kind: str, req: FeatureCollectionRequest) -> Response:
    try:
        content, media_type, filename = export_collection(req.feature_collection, kind)
    except KeyError as exc:
        raise HTTPException(404, f"unsupported export kind: {kind}") from exc
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/state")
def current_state() -> dict[str, Any]:
    return store.state()


@app.get("/api/diagnostics/babice-failure-demo")
def babice_failure_demo() -> dict[str, Any]:
    class Rect:
        x0 = 0
        y0 = 0
        x1 = 1191.005
        y1 = 1683.751

    diagnostics = diagnostics_from_drawings(
        page_count=1,
        page_width=1191.005,
        page_height=1683.751,
        drawings=[{"fill": (1.0, 1.0, 1.0), "items": [("re", Rect())]}],
        images_count=0,
        text_label_candidates=0,
        raster_image_coverage_ratio=0,
    )
    return diagnostic_failure_collection(
        name="babice_z12_full_page_white_failure",
        source_url="demo:babice-z12",
        diagnostics=diagnostics,
        selected_algorithm="diagnostic_only_v1",
    )
