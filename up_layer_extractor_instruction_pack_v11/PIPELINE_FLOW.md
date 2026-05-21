# Extraction pipeline flow v9

## High-level flow

```text
PDF / URL / upload
→ up_import.pdf_source
→ up_import.pdf_page
→ up_import.vector_import
→ up_import.legend_crop
→ up_stg.vector_def_candidate + up_stg.up_text_def_candidate
→ selected up_import.vector_def + up_import.up_text_def
→ up_stg.vector_stg_candidates
→ up_stg.vector_stg_single_polygon
→ up_stg.vector_stg_text_assignment
→ up_stg.vector_stg_residual
→ up_manual.vector_review / polygon_edit_session / polygon_annotation
→ up_core.up_def / up_core.up_type_def / up_core.vector_output
→ up_api.vector_output_geojson
```

## Stage 1: vector_import

`vector_import` is the raw PDF drawings extract.

It stores:
- PDF drawing geometry
- fill
- stroke
- dash
- opacity
- hatch/pattern
- geom type
- z-order
- raw path operations

No business classification is allowed here.

## Stage 2: vector_def

`vector_def` says what a style means.

Example:
- fill `#ff0000`
- stroke maybe null
- geom type polygon
- legend crop says `BI plochy stabilizované`
- maps to `RZVP / BI / STAV`
- links to `up_type_id`

## Stage 3: up_text_def

`up_text_def` says how labels are detected and assigned.

Example:
- regex: `Z[0-9]+`
- role: `change_label`
- type: `NAVRH`
- association: nearest polygon / inside region / dotted boundary region

## Stage 4: vector_stg_*

Staging turns raw import + definitions into candidate polygons.

Rules:
- Split all multipolygons into single polygons.
- Keep diagnostics.
- Keep source IDs.
- Keep uncertainty.
- Do not promote review candidates directly to core.

## Stage 5: manual

Humans approve, reject or correct.

## Stage 6: vector_output

Only approved final features go here.

Each feature has:
- `up_id`
- `up_type_id`
- `FID`
- `LAYER`
- `CLASS`
- `TYPE`
- `LAYER_CLASS`
- `class_type`
- `text_id`
- `IS_CLOSED`
- geometry


## v9: legend auto-generation

Definition creation is now a pipeline, not a manual hardcoded file:

```text
observed raw styles + legend crops
→ vector_def_candidate / up_text_def_candidate
→ operator selection
→ active vector_def / up_text_def
→ classified extraction
```

The UI must show candidate definitions with legend screenprint evidence and all exposed style fields.

## v9: manual border adjustment

Selected polygon editing is allowed only as a manual correction layer:

```text
staging polygon
→ manual edit session
→ approved correction
→ core vector_output
```

Raw import and staging rows must stay reproducible.

## v9: polygon labels and notes

Labels and notes belong in `up_manual.polygon_annotation`.

Do not overwrite extracted `text_id` when adding manual notes.

## v9: validation after manual correction

Every manual edit must run geometry checks:
- single Polygon
- closed exterior ring
- valid geometry
- area delta threshold
- provenance retained


## v10 remapping stage

After vector/text/legend definitions are extracted and before `up_core.vector_output` is finalized, run a semantic remapping stage:

1. Load active `up_import.class_remap_config`.
2. For each `vector_def` and `up_text_def`, compute candidate mapping into canonical fields.
3. Save proposals to `up_stg.class_remap_candidate`.
4. Apply profile-specific mappings where available.
5. Apply manual overrides from `up_manual.class_remap_override`.
6. Emit final canonical fields into `up_core.vector_output`:
   - `LAYER`
   - `CLASS`
   - `TYPE`
   - `LAYER_CLASS`
   - `class_type`
   - `group_label`
   - `display_label`

Unknown or ambiguous mappings must remain visible in the UI and block final approval unless explicitly accepted as `CUST.*` with a `REF`.
