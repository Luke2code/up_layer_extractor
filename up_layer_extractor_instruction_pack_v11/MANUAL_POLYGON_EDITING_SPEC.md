# Manual polygon editing and annotation spec

## Purpose

Allow the operator to adjust the border of a selected polygon without destroying algorithm provenance.

## UI behavior

Selected polygon tools:
- select polygon by click
- yellow/dark-grey selected border remains visible
- edit mode toggle: `Edit border`
- vertex handles appear only in edit mode
- drag vertex
- add vertex on edge
- delete selected vertex
- split polygon if needed only through an explicit action
- save correction
- cancel correction
- add label
- add note
- mark status: `approved`, `needs_fix`, `rejected`, `review_required`

Keyboard:
- `ESC` clears selection or exits edit mode
- `Ctrl+Z` undo current edit session
- `Enter` save current edit session when focused in map edit mode

## Data rules

Manual edits must be stored as corrections:

```text
up_stg.vector_stg_single_polygon.geom_page_original
+ up_manual.polygon_edit_session.geom_page_corrected
→ up_core.vector_output.geom_page only after approval
```

Never overwrite:
- `up_import.vector_import.geom_page`
- `up_stg.vector_stg_single_polygon.geom_page_original`

## Required fields for edit session

`up_manual.polygon_edit_session`:
- `manual_edit_id`
- `up_id`
- `stg_polygon_id`
- `fid` nullable until final output
- `edit_status`: `draft`, `submitted`, `approved`, `rejected`, `superseded`
- `edit_reason`: text
- `geom_page_before`
- `geom_page_after`
- `area_before_page_units`
- `area_after_page_units`
- `area_delta_pct`
- `is_closed_after`
- `is_valid_after`
- `created_by`
- `created_at`
- `updated_at`

Optional detailed audit:
`up_manual.polygon_vertex_edit`:
- `vertex_edit_id`
- `manual_edit_id`
- `operation`: `move_vertex`, `add_vertex`, `delete_vertex`, `split`, `merge`, `reshape`
- `vertex_index`
- `point_before`
- `point_after`
- `created_at`

## Polygon labels and notes

`up_manual.polygon_annotation`:
- `annotation_id`
- `up_id`
- `stg_polygon_id` nullable
- `vector_output_id` nullable
- `annotation_type`: `label`, `note`, `warning`, `decision`
- `label_text`
- `note_text`
- `created_by`
- `created_at`
- `updated_at`
- `is_active`

Rules:
- `text_id` remains extracted source label.
- `label_text` or `label_override` is human-facing/manual.
- Do not overwrite `text_id` when adding a note.

## Validation after manual edit

Every saved correction must validate:
- geometry type is `Polygon`
- exterior ring is closed
- geometry is valid or repaired with explicit warning
- no self-intersection accepted silently
- area delta above threshold requires reviewer note
- final output keeps `manual_edit_id`
