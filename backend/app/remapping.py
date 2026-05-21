from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


TYPE_BY_CODE = {"1": "STAV", "2": "NAVRH", "3": "REZERVA"}
TYPE_CODE_BY_NAME = {value: key for key, value in TYPE_BY_CODE.items()}


@dataclass(frozen=True)
class RemapResult:
    raw_layer: str | None
    raw_class: str | None
    raw_type_text: str | None
    proposed_layer: str
    proposed_class: str
    proposed_type: str
    proposed_layer_class: str
    proposed_class_type: str
    group_label: str | None
    display_label: str | None
    matched_rule: str
    match_score: float
    requires_manual_review: bool
    reason: str

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RemapConfig:
    version: str
    source: str
    class_type_config: dict[str, list[str]]
    class_group_map: dict[str, str]
    class_map: dict[str, str]

    @classmethod
    def load(cls, path: str | Path) -> "RemapConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            version=str(data["version"]),
            source=str(data["source"]),
            class_type_config=data["CLASS_TYPE_CONFIG"],
            class_group_map=data["CLASS_GROUP_MAP"],
            class_map=data["CLASS_MAP"],
        )


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.casefold()


def _evidence_matches(pattern: str, evidence: str) -> bool:
    folded_pattern = _fold(pattern).replace("?", ".*")
    folded_evidence = _fold(evidence)
    return re.search(folded_pattern, folded_evidence) is not None


def infer_type(raw_type_text: str | None, config: RemapConfig, layer: str | None = None) -> tuple[str, str, float, bool]:
    if layer == "ZMEN" and not raw_type_text:
        return "NAVRH", "ZMEN default TYPE=NAVRH", 0.9, False
    if not raw_type_text:
        return "UNMAPPED", "missing type evidence", 0.0, True

    upper = raw_type_text.upper()
    if upper in TYPE_CODE_BY_NAME:
        return upper, f"exact TYPE={upper}", 1.0, False

    matches: list[tuple[str, str]] = []
    for code, patterns in config.class_type_config.items():
        for pattern in patterns:
            if _evidence_matches(pattern, raw_type_text):
                matches.append((code, pattern))
                break

    if len(matches) == 1:
        code, pattern = matches[0]
        return TYPE_BY_CODE[code], f"CLASS_TYPE_CONFIG[{code}] {pattern}", 0.82, False
    if len(matches) > 1:
        names = ",".join(TYPE_BY_CODE[code] for code, _ in matches)
        return "UNMAPPED", f"ambiguous type evidence {names}", 0.2, True
    return "UNMAPPED", "no type evidence matched", 0.1, True


def class_type_value(cls: str, typ: str) -> str:
    suffix = TYPE_CODE_BY_NAME.get(typ.upper(), "0")
    return f"{cls}.{suffix}"


def _longest_prefix_match(value: str, lookup: dict[str, str]) -> tuple[str, str] | None:
    matches = [(key, label) for key, label in lookup.items() if value.startswith(key)]
    if not matches:
        return None
    return max(matches, key=lambda item: len(item[0]))


def remap_class(
    *,
    layer: str | None,
    class_name: str | None,
    raw_type_text: str | None,
    config: RemapConfig,
    ref: str | None = None,
    manual_override: dict[str, str] | None = None,
) -> RemapResult:
    if manual_override:
        override_layer = manual_override["layer"]
        override_class = manual_override["class"]
        override_type = manual_override["type"]
        layer_class = manual_override.get("layer_class") or f"{override_layer}.{override_class}"
        return RemapResult(
            raw_layer=layer,
            raw_class=class_name,
            raw_type_text=raw_type_text,
            proposed_layer=override_layer,
            proposed_class=override_class,
            proposed_type=override_type,
            proposed_layer_class=layer_class,
            proposed_class_type=manual_override.get("class_type") or class_type_value(override_class, override_type),
            group_label=manual_override.get("group"),
            display_label=manual_override.get("label"),
            matched_rule="manual_override",
            match_score=1.0,
            requires_manual_review=False,
            reason="manual override wins over automatic mapping",
        )

    raw_layer = layer or "UNCLASSIFIED"
    raw_class = class_name or "UNMAPPED"
    raw_layer_class = f"{raw_layer}.{raw_class}"
    proposed_type, type_rule, type_score, type_review = infer_type(raw_type_text, config, raw_layer)

    display_label = config.class_map.get(raw_layer_class)
    group = None
    group_match = _longest_prefix_match(raw_layer_class, config.class_group_map)
    if group_match:
        group = group_match[1]

    if display_label:
        requires_review = type_review
        if raw_layer_class.startswith("CUST.") and not ref:
            requires_review = True
        return RemapResult(
            raw_layer=layer,
            raw_class=class_name,
            raw_type_text=raw_type_text,
            proposed_layer=raw_layer,
            proposed_class=raw_class,
            proposed_type=proposed_type,
            proposed_layer_class=raw_layer_class,
            proposed_class_type=class_type_value(raw_class, proposed_type),
            group_label=group,
            display_label=display_label if not ref else f"{display_label} ({ref})",
            matched_rule=f"CLASS_MAP exact; {type_rule}",
            match_score=min(0.96, 0.75 + type_score / 4),
            requires_manual_review=requires_review,
            reason="exact class map match" if not requires_review else "mapping requires operator review",
        )

    if raw_layer_class.startswith("CUST.") and ref:
        return RemapResult(
            raw_layer=layer,
            raw_class=class_name,
            raw_type_text=raw_type_text,
            proposed_layer=raw_layer,
            proposed_class=raw_class,
            proposed_type=proposed_type,
            proposed_layer_class=raw_layer_class,
            proposed_class_type=class_type_value(raw_class, proposed_type),
            group_label=group,
            display_label=f"{raw_layer_class} - {ref}",
            matched_rule=f"CUST REF; {type_rule}",
            match_score=0.78,
            requires_manual_review=type_review,
            reason="custom class accepted with REF evidence",
        )

    return RemapResult(
        raw_layer=layer,
        raw_class=class_name,
        raw_type_text=raw_type_text,
        proposed_layer=raw_layer,
        proposed_class="UNMAPPED",
        proposed_type=proposed_type,
        proposed_layer_class=f"{raw_layer}.UNMAPPED",
        proposed_class_type=class_type_value("UNMAPPED", proposed_type),
        group_label=group,
        display_label=None,
        matched_rule=f"UNMAPPED; {type_rule}",
        match_score=type_score / 2,
        requires_manual_review=True,
        reason="class is not in active CLASS_MAP and no explicit custom override exists",
    )


def remap_feature_properties(props: dict[str, Any], config: RemapConfig) -> dict[str, Any]:
    result = remap_class(
        layer=props.get("LAYER"),
        class_name=props.get("CLASS"),
        raw_type_text=props.get("TYPE") or props.get("legend_symbol"),
        config=config,
    )
    mapped = result.model_dump()
    mapped["FID"] = props.get("FID")
    return mapped

