from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class ExtractRequest(BaseModel):
    url: HttpUrl
    profile_id: str | None = None


class FeatureCollectionRequest(BaseModel):
    feature_collection: dict[str, Any]


class DefinitionApprovalRequest(BaseModel):
    candidate_id: str
    kind: Literal["vector", "text"]
    approved_by: str = "operator"


class ManualEditRequest(BaseModel):
    up_id: str
    stg_polygon_id: str
    fid: int | None = None
    edit_reason: str | None = None
    geom_page_before: dict[str, Any]
    geom_page_after: dict[str, Any]
    created_by: str = "operator"
    review_note: str | None = None


class AnnotationRequest(BaseModel):
    up_id: str
    stg_polygon_id: str | None = None
    vector_output_id: str | None = None
    annotation_type: Literal["label", "note", "warning", "decision"]
    label_text: str | None = None
    note_text: str | None = None
    created_by: str = "operator"
    is_active: bool = True


class RemapPreviewRequest(BaseModel):
    layer: str | None = Field(default=None, alias="LAYER")
    class_name: str | None = Field(default=None, alias="CLASS")
    type_text: str | None = Field(default=None, alias="TYPE")
    ref: str | None = None

    model_config = {"populate_by_name": True}


class RemapOverrideRequest(BaseModel):
    run_id: str = "local-ui"
    target_kind: Literal["vector_def", "text_def", "feature", "profile"]
    target_id: str
    override_layer: str
    override_class: str
    override_type: str
    override_group: str | None = None
    override_label: str | None = None
    note: str
    created_by: str = "operator"


class HealthResponse(BaseModel):
    ok: bool
    service: str
    version: str

