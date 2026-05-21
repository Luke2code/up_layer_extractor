# Remapping Validation Tests — v10

Required tests for Codex implementation.

## Unit tests

1. `class_type_from_type_text`
   - text containing `stav` -> `TYPE=STAV`, suffix `.1`
   - text containing `návrh` or `zastaviteln` -> `TYPE=NAVRH`, suffix `.2`
   - text containing `rezerv` -> `TYPE=REZERVA`, suffix `.3`

2. `class_map_exact_match`
   - `RZVP.BI` -> display label `BI - bydlení individuální`
   - `RZVP.SV` -> display label `SV - smíšené obytné venkovské`
   - `ZMEN.Z` -> display label `ZMEN.Z - Zastavitelná plocha`
   - `ZMEN.T` -> display label `ZMEN.T - Transformační plocha`

3. `class_group_prefix_match`
   - `RZVP.BI` -> group `B - Bydlení`
   - `RZVP.SV` -> group `S - Smíšené Obytné`
   - `PODM.US` -> group `PODM / REGU`
   - unknown -> `UNMAPPED`, `requires_manual_review=true`

4. `manual_override_precedence`
   - override wins over profile and config mapping
   - override is recorded with target id and note

## Integration tests

1. Květnice regression remains stable.
2. Babice full-page white background is rejected as fake success.
3. Unknown/ambiguous mapping appears in review queue.
4. Final `up_core.vector_output` contains `LAYER`, `CLASS`, `TYPE`, `LAYER_CLASS`, `class_type`, `display_label`, and `group_label`.
