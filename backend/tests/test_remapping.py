from __future__ import annotations

from pathlib import Path

from backend.app.remapping import RemapConfig, class_type_value, infer_type, remap_class


CONFIG = RemapConfig.load(Path(__file__).resolve().parents[2] / "config" / "vector_layer_class_type_remap.json")


def test_class_type_config_supports_stav_navrh_rezerva() -> None:
    assert infer_type("stabilizovane plochy", CONFIG)[0] == "STAV"
    assert infer_type("návrh změny", CONFIG)[0] == "NAVRH"
    assert infer_type("uzemni rezerva", CONFIG)[0] == "REZERVA"
    assert class_type_value("BI", "STAV") == "BI.1"
    assert class_type_value("Z", "NAVRH") == "Z.2"
    assert class_type_value("R", "REZERVA") == "R.3"


def test_known_classes_resolve() -> None:
    for layer, cls, expected_label in [
        ("RZVP", "BI", "BI - bydlení individuální"),
        ("RZVP", "SV", "SV - smíšené obytné venkovské"),
        ("ZMEN", "Z", "ZMEN.Z - Zastavitelná plocha"),
        ("ZMEN", "T", "ZMEN.T - Transformační plocha"),
    ]:
        result = remap_class(layer=layer, class_name=cls, raw_type_text="STAV" if layer == "RZVP" else None, config=CONFIG)
        assert result.display_label == expected_label
        assert result.requires_manual_review is False


def test_custom_and_unknown_review_rules() -> None:
    custom_without_ref = remap_class(layer="CUST", class_name="X", raw_type_text="navrh", config=CONFIG)
    assert custom_without_ref.requires_manual_review is True

    custom_with_ref = remap_class(layer="CUST", class_name="X", raw_type_text="navrh", ref="local legend label", config=CONFIG)
    assert custom_with_ref.proposed_layer_class == "CUST.X"
    assert custom_with_ref.requires_manual_review is False

    unknown = remap_class(layer="RZVP", class_name="QQ", raw_type_text="stav", config=CONFIG)
    assert unknown.proposed_class == "UNMAPPED"
    assert unknown.requires_manual_review is True


def test_manual_override_wins() -> None:
    result = remap_class(
        layer="RZVP",
        class_name="QQ",
        raw_type_text="stav",
        config=CONFIG,
        manual_override={
            "layer": "RZVP",
            "class": "BI",
            "type": "STAV",
            "group": "B - Bydlení",
            "label": "BI - bydlení individuální",
        },
    )
    assert result.matched_rule == "manual_override"
    assert result.proposed_layer_class == "RZVP.BI"
    assert result.requires_manual_review is False

