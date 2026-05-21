# Custom Layer / Class / Type Remapping — v10

## Purpose
The extractor must not hardcode only the Květnice sample classes. It needs a configurable remapping layer that can normalize legacy labels, municipality-specific legend labels, and user corrections into the canonical output contract.

This v10 pack incorporates the uploaded `vector_config` mapping as a first-class configuration source.

## Source concepts imported

### CLASS_TYPE_CONFIG
Maps textual evidence to numeric type codes:

| type_code | canonical TYPE | matching evidence |
|---:|---|---|
| 1 | `STAV` | `stav`, `stabil?`, `zastavěn?` |
| 2 | `NAVRH` | `navrh`, `návrh`, `změna`, `zastaviteln?` |
| 3 | `REZERVA` | `rezerv?` |

Production rule:
- `TYPE=STAV` -> `class_type = CLASS.1`
- `TYPE=NAVRH` -> `class_type = CLASS.2`
- `TYPE=REZERVA` -> `class_type = CLASS.3`, only if explicitly supported by the source/profile.
- For current `ZMEN`, keep `TYPE=NAVRH` unless the selected definition explicitly maps otherwise.

### CLASS_GROUP_MAP
Maps high-level `LAYER.CLASS` prefixes to UI groups and review buckets, for example:
- `RZVP.B*` -> bydlení group
- `RZVP.S*` -> smíšené obytné group
- `ZMEN.Z` / `ZMEN.T` -> main change-area groups
- `PODM.*` / `REGU.*` -> regulation/condition group
- `CUST.*` -> custom user-defined mapping requiring `REF`

### CLASS_MAP
Maps concrete `LAYER.CLASS` definitions to human-readable labels. This must drive:
- Definition Explorer display names
- manual remapping dropdowns
- review labels
- `up_core.up_type_def` seed/reference rows
- validation messages

Examples:
- `RZVP.BI` -> `BI - bydlení individuální`
- `RZVP.SV` -> `SV - smíšené obytné venkovské`
- `ZMEN.Z` -> `ZMEN.Z - Zastavitelná plocha`
- `ZMEN.T` -> `ZMEN.T - Transformační plocha`
- `CUST.X` -> custom class; must require `REF` / manual label.

## Required data model additions

### up_import.class_remap_config
Stores imported config versions.

Required fields:
- `config_id`
- `config_name`
- `version`
- `source_ref`
- `class_type_config jsonb`
- `class_group_map jsonb`
- `class_map jsonb`
- `is_active boolean`
- `created_at`

### up_stg.class_remap_candidate
Stores automatic mapping proposals per vector/text/legend definition.

Required fields:
- `candidate_id`
- `run_id`
- `vector_def_id nullable`
- `up_text_def_id nullable`
- `raw_layer nullable`
- `raw_class nullable`
- `raw_type_text nullable`
- `proposed_layer`
- `proposed_class`
- `proposed_type`
- `proposed_layer_class`
- `proposed_class_type`
- `matched_rule`
- `match_score numeric`
- `requires_manual_review boolean`
- `reason text`

### up_manual.class_remap_override
Stores operator corrections.

Required fields:
- `override_id`
- `run_id`
- `target_kind` (`vector_def`, `text_def`, `feature`, `profile`)
- `target_id`
- `override_layer`
- `override_class`
- `override_type`
- `override_layer_class`
- `override_class_type`
- `override_group`
- `override_label`
- `note`
- `created_by`
- `created_at`

## Remapping precedence

1. Explicit manual override (`up_manual.class_remap_override`).
2. Selected profile mapping for the PDF/municipality.
3. Active `up_import.class_remap_config` exact `CLASS_MAP` match.
4. Prefix group match from `CLASS_GROUP_MAP`.
5. Type evidence from `CLASS_TYPE_CONFIG`.
6. `UNMAPPED` + `requires_manual_review=true`.

Do not silently coerce unknown classes. Unknown means unknown.

## UI requirements

Add a `Remapping` tab or panel:
- show raw detected layer/class/type evidence
- show proposed canonical `LAYER`, `CLASS`, `TYPE`, `LAYER_CLASS`, `class_type`
- show group and display label from config
- allow operator override
- require note for `CUST.*` or unknown mapping
- show mapping confidence and matched rule

Definition Explorer must expose mapping on both tables:
- Vector Definitions table: style -> proposed class/type -> selected mapping
- Text Definitions table: text regex/label -> proposed type/class -> selected mapping

## Validation gates

Fail or require review if:
- `CLASS` is not in active `CLASS_MAP` and no explicit custom override exists.
- `TYPE` evidence is ambiguous (`STAV` and `NAVRH` both matched).
- `class_type` does not match `TYPE` code.
- `ZMEN` has fill-source classification without an explicit source rule; ZMEN generally has no fill and must be boundary/text driven.
- `CUST.*` is used without `REF` / manual label.

## Important non-goals

Do not make this a giant hardcoded if/else block in extractor code. Treat remapping as data/config, persisted in DB and editable in UI.
