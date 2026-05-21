from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .geometry import geometry_bbox, normalize_feature_properties, validate_manual_polygon_edit
from .remapping import RemapConfig, remap_feature_properties


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class InMemoryStore:
    remap_config: RemapConfig
    vector_def_candidates: dict[str, dict[str, Any]] = field(default_factory=dict)
    text_def_candidates: dict[str, dict[str, Any]] = field(default_factory=dict)
    approved_vector_defs: dict[str, dict[str, Any]] = field(default_factory=dict)
    approved_text_defs: dict[str, dict[str, Any]] = field(default_factory=dict)
    manual_edits: dict[str, dict[str, Any]] = field(default_factory=dict)
    annotations: dict[str, dict[str, Any]] = field(default_factory=dict)
    legend_label_corrections: dict[str, dict[str, Any]] = field(default_factory=dict)
    remap_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    _counters: dict[str, int] = field(default_factory=dict)

    def next_id(self, prefix: str) -> str:
        value = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = value
        return f"{prefix}-{value:04d}"

    def generate_definition_candidates(self, feature_collection: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        features = feature_collection.get("features") or []
        vector_seen: set[tuple[Any, ...]] = set()
        text_seen: set[tuple[Any, ...]] = set()
        vector_candidates: list[dict[str, Any]] = []
        text_candidates: list[dict[str, Any]] = []

        for feature in features:
            props = normalize_feature_properties(feature)
            style_key = props.get("style_hex") or props.get("source_style_hex") or "not_exposed"
            vector_key = (
                style_key,
                props.get("LAYER"),
                props.get("CLASS"),
                props.get("TYPE"),
                props.get("has_fill_color"),
            )
            if vector_key not in vector_seen:
                vector_seen.add(vector_key)
                mapped = remap_feature_properties(props, self.remap_config)
                candidate_id = self.next_id("vector-def-candidate")
                candidate = {
                    "vector_def_candidate_id": candidate_id,
                    "candidate_id": candidate_id,
                    "up_id": props.get("up_id") or "kvetnice-regression",
                    "source_style_key": style_key,
                    "legend_screenprint": props.get("legend_symbol") or "not_exposed",
                    "legend_label_text": props.get("legend_symbol"),
                    "fill_hex": props.get("style_hex") or props.get("source_style_hex"),
                    "stroke_hex": props.get("source_stroke_hex"),
                    "stroke_width": props.get("stroke_width"),
                    "dash_array": props.get("dash_array"),
                    "fill_opacity": props.get("fill_opacity"),
                    "hatch_or_pattern": props.get("hatch_or_pattern"),
                    "geom_type": (feature.get("geometry") or {}).get("type"),
                    "z_index": props.get("z_index"),
                    "sample_bbox_page": props.get("bbox_page_pt") or geometry_bbox(feature.get("geometry")),
                    "sample_count": 1,
                    "candidate_layer": props.get("LAYER"),
                    "candidate_class": props.get("CLASS"),
                    "candidate_type": props.get("TYPE"),
                    "candidate_up_type_id": props.get("up_type_id"),
                    "mapping": mapped,
                    "confidence": props.get("confidence") or "candidate",
                    "candidate_status": "candidate",
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
                self.vector_def_candidates[candidate_id] = candidate
                vector_candidates.append(candidate)

            text_id = props.get("text_id")
            if text_id:
                text_key = (props.get("LAYER"), props.get("CLASS"), props.get("TYPE"), str(text_id))
                if text_key not in text_seen:
                    text_seen.add(text_key)
                    candidate_id = self.next_id("text-def-candidate")
                    candidate = {
                        "up_text_def_candidate_id": candidate_id,
                        "candidate_id": candidate_id,
                        "up_id": props.get("up_id") or "kvetnice-regression",
                        "text_role": "change_label" if props.get("LAYER") == "ZMEN" else "source_label",
                        "regex_pattern": r"^(Z|P|K)[0-9]+(?:/[0-9]+)?$",
                        "sample_text": text_id,
                        "sample_count": 1,
                        "font_name": "not_exposed",
                        "font_size_min": None,
                        "font_size_max": None,
                        "font_color_hex": None,
                        "rotation": None,
                        "sample_bbox_page": props.get("text_bbox_page"),
                        "association_strategy": "inside_polygon_or_nearest_boundary",
                        "candidate_layer": props.get("LAYER"),
                        "candidate_class": props.get("CLASS"),
                        "candidate_type": props.get("TYPE"),
                        "mapping": remap_feature_properties(props, self.remap_config),
                        "candidate_status": "candidate",
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    }
                    self.text_def_candidates[candidate_id] = candidate
                    text_candidates.append(candidate)

        return {"vector_definitions": vector_candidates, "text_definitions": text_candidates}

    def approve_definition(self, candidate_id: str, kind: str, approved_by: str) -> dict[str, Any]:
        source = self.vector_def_candidates if kind == "vector" else self.text_def_candidates
        approved = self.approved_vector_defs if kind == "vector" else self.approved_text_defs
        if candidate_id not in source:
            raise KeyError(candidate_id)
        candidate = dict(source[candidate_id])
        candidate["candidate_status"] = "approved"
        candidate["definition_status"] = "approved"
        candidate["approved_by"] = approved_by
        candidate["approved_at"] = now_iso()
        source[candidate_id] = candidate
        approved[candidate_id] = candidate
        return candidate

    def create_manual_edit(self, payload: dict[str, Any]) -> dict[str, Any]:
        validation = validate_manual_polygon_edit(payload["geom_page_before"], payload["geom_page_after"])
        if validation.errors:
            raise ValueError("; ".join(validation.errors))
        if validation.review_note_required and not payload.get("review_note"):
            raise ValueError("review_note is required when area delta exceeds threshold")

        manual_edit_id = self.next_id("manual-edit")
        record = {
            "manual_edit_id": manual_edit_id,
            "up_id": payload["up_id"],
            "stg_polygon_id": payload["stg_polygon_id"],
            "fid": payload.get("fid"),
            "edit_status": "saved",
            "edit_reason": payload.get("edit_reason"),
            "geom_page_before": payload["geom_page_before"],
            "geom_page_after": payload["geom_page_after"],
            "area_before_page_units": validation.area_before,
            "area_after_page_units": validation.area_after,
            "area_delta_pct": validation.area_delta_pct,
            "is_closed_after": validation.is_closed_after,
            "is_valid_after": validation.is_valid_after,
            "review_note": payload.get("review_note"),
            "created_by": payload.get("created_by", "operator"),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.manual_edits[manual_edit_id] = record
        return record

    def create_annotation(self, payload: dict[str, Any]) -> dict[str, Any]:
        annotation_id = self.next_id("annotation")
        record = {
            "annotation_id": annotation_id,
            "up_id": payload["up_id"],
            "stg_polygon_id": payload.get("stg_polygon_id"),
            "vector_output_id": payload.get("vector_output_id"),
            "annotation_type": payload["annotation_type"],
            "label_text": payload.get("label_text"),
            "note_text": payload.get("note_text"),
            "created_by": payload.get("created_by", "operator"),
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "is_active": payload.get("is_active", True),
        }
        self.annotations[annotation_id] = record
        return record

    def create_legend_label_correction(self, payload: dict[str, Any]) -> dict[str, Any]:
        correction_id = self.next_id("legend-label-correction")
        record = {
            "legend_label_correction_id": correction_id,
            "collection_id": payload.get("collection_id"),
            "legend_item_id": payload.get("legend_item_id"),
            "legend_row_id": payload.get("legend_row_id"),
            "legend_crop_id": payload.get("legend_crop_id"),
            "code_text": payload.get("code_text"),
            "original_raw_label": payload.get("original_raw_label"),
            "corrected_label": payload.get("corrected_label"),
            "reason": payload.get("reason"),
            "created_by": payload.get("created_by", "operator-ui"),
            "created_at": now_iso(),
            "review_status": "manual_label_saved_requires_approval",
        }
        self.legend_label_corrections[correction_id] = record
        return record

    def create_remap_override(self, payload: dict[str, Any]) -> dict[str, Any]:
        override_id = self.next_id("remap-override")
        record = {
            "override_id": override_id,
            "override_layer_class": f"{payload['override_layer']}.{payload['override_class']}",
            "override_class_type": payload.get("override_class_type"),
            "created_at": now_iso(),
            **payload,
        }
        self.remap_overrides[override_id] = record
        return record

    def state(self) -> dict[str, Any]:
        return {
            "vector_def_candidates": list(self.vector_def_candidates.values()),
            "text_def_candidates": list(self.text_def_candidates.values()),
            "approved_vector_defs": list(self.approved_vector_defs.values()),
            "approved_text_defs": list(self.approved_text_defs.values()),
            "manual_edits": list(self.manual_edits.values()),
            "annotations": list(self.annotations.values()),
            "legend_label_corrections": list(self.legend_label_corrections.values()),
            "remap_overrides": list(self.remap_overrides.values()),
        }
