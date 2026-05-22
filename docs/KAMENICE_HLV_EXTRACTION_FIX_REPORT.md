# Kamenice HLV Extraction Fix Report

Date: 2026-05-21

## Root Cause

Kamenice HLV is a vector PDF, but its filled map areas are emitted as tens of thousands of tiny positive-area path fragments. The previous extractor only checked that closed positive polygons existed, so it reported a false success: 56,642 raw stripe/tessellation fragments were exposed as primary features.

The failure signature is now detected explicitly:

- raw fragment count: 56,642
- median fragment area: 8.6684 pt2
- median fragment bbox height: 2.0399 pt
- triangular fragment ratio: 0.9965
- tiny fragment ratio: 0.6520
- primary mode after fix: `merged_polygons`
- primary feature count after fix: 1,265

## Implementation Approaches Recorded

1. `baseline_raw_positive_polygon_count_v1`
   Measured the old false-success state before editing. Positive closed polygons alone are no longer accepted as sufficient evidence.

2. `solid_dash_pattern_normalization_v2`
   Fixed PyMuPDF dash parsing so `[] 0`, `[] 0.0`, `[]`, `0`, and empty values normalize to `solid` and do not create false dash evidence.

3. `right_panel_text_density_region_v1`
   Separates map body from legend/title areas using page dimensions, right-panel text density, and bbox overlap.

4. `stripe_fragment_detector_v1`
   Adds a visual/geometry quality gate over raw features: fragment count, median area/height, tiny ratio, triangular ratio, style density, and horizontal band alignment.

5. `vector_tessellated_fill_merge_v1`
   Groups map-body fragments by source style and uses guarded Shapely `unary_union` to create primary merged polygon candidates. Raw fragments are retained only as debug samples.

6. `raw_fragment_false_success_gate_v1`
   Fails the old condition where tens of thousands of raw fragments could be presented as the trusted output.

7. `right_panel_autocrop_render_v1`
   Renders an actual legend crop artifact under `docs/legend_crops/`.

8. `target_code_row_inventory_v1`
   Exposes legend row records for B/BI/BV/BH/BU/BX.c/BX.p/BX.r/R/RI/RX/S/SO/SV/SC/SX, with review flags when the target code was not confirmed inside the autocrop.

9. `target_left_legend_autocrop_render_v1`
   Replaces the generic right-panel legend hit for Kamenice HLV with a target-code cluster search on the left legend. The crop stores both the rendered image artifact and page-to-image transform metadata for overlays.

10. `target_code_row_symbol_split_v1`
   Splits each target legend row into symbol positions. The first supported symbol is `stav_stabil` / class type id `1`; the second supported symbol is `navrh` / class type id `2`.

11. `legend_item_two_symbol_vector_def_split_v1`
   Creates separate vector definition rows for detected supported symbols. Missing expected symbols are recorded as `missing_expected_symbol_requires_review` and are not fabricated as normal vector definitions.

12. `fake_legend_provider_v1`
   Emits review proposals for unreviewed legend items so the UI can trace later agent/provider suggestions separately from extraction truth.

13. `bbox_contains_or_nearest_target_text_v1`
   Adds spatial text association metadata for merged features where target code labels are inside or near the merged bbox.

14. `operator_bbox_fallback_v1`
    Adds a manual legend crop fallback record so the UI can surface the suggested bbox when autocrop needs correction.

15. `legend_symbol_overlay_pointer_passthrough_v1`
    Fixes the UI checkbox hit-test failure found during smoke testing by making symbol overlay badges non-interactive, leaving legend row focus and checkbox controls clickable.

16. `fragment_role_classification_v1`
    Classifies raw fragments before merge as area/tessellated fill, hatch, text mask, legend symbol, background mask, linework, or unknown. Trusted merged polygons now use only area-fill and tessellated-area roles by default.

17. `visual_artifact_diagnostics_v1`
    Records white/background candidates, rectangular hole metrics, spike/needle/sliver/thin-corridor metrics, and review flags instead of visually hiding artifacts.

18. `selected_polygon_proposal_annotation_v1`
    Adds raw fields, proposed mapping fields, classification reason, matched legend/vector definition ids, artifact flags, and export-blocking reason to selected polygon properties.

19. `pymupdf_page_render_snapshot_v1`
    Renders the selected PDF page to a Plan PNG artifact with page-to-image and image-to-page transform metadata. Vector PDFs no longer report `Plan (no raster)` when the original page can be rendered.

20. `display_color_source_style_v1`
    Preserves source fill/stroke and legend symbol color evidence on merged polygons. Human review defaults to source colors instead of generic grey.

21. `void_artifact_review_flagging_v1`
    Detects triangular/small voids and records review-only cleanup metadata without mutating raw or staging geometries.

22. `legend_label_quality_gate_v1`
    Keeps raw garbled PDF text in diagnostics but exposes cleaned display labels, review-required agent proposals, and manual label correction records in the UI.

## Validation

Dedicated Kamenice validation:

- command: `PYTHONPATH=/mnt/c/coding/up_layer_extractor .venv/bin/python scripts/validate_kamenice_hlv.py`
- status: passed
- output: `docs/kamenice_hlv_validation.json`
- legend crop artifact: `docs/legend_crops/collection-76c48f91822e_legend_0001.png`
- legend items: 10
- legend symbols: 20
- legend-linked vector definitions: 16
- two-symbol legend splits: 6
- missing expected symbols requiring review: 4
- spatial associations created: 875
- fragment role counts: tessellated area 56,464; area fill 73; legend symbol 71; unknown 34
- white/background trusted output count: 0
- rectangular holes: 18; rectangular hole area ratio: 0.000007
- max spike score: 0.5957; needle count: 0; sliver component count: 1; thin corridor count: 8
- selected polygon proposal annotations: 875

Full PDF corpus validation:

- command: `PYTHONPATH=/mnt/c/coding/up_layer_extractor .venv/bin/python scripts/validate_pdf_corpus.py`
- status: 8 passed, 1 missing local input (`/mnt/c/Users/Me/Downloads/kamenice zcu.pdf`)
- output: `docs/pdf_validation_corpus.json` and `docs/pdf_validation_corpus.csv`

Corpus feature counts after the fix:

| PDF | Primary mode | Raw fragments | Primary features | Tessellated |
| --- | --- | ---: | ---: | --- |
| UP__MNICHOVICE__538493__UZ_1__HLV.PDF | raw_polygons | 2,236 | 2,236 | false |
| UP__SVETICE___A_PV__538841___UZ_1_HLV.pdf | merged_polygons | 19,363 | 368 | true |
| UP_538728_RICANY_HLV.pdf | raw_polygons | 49,967 | 49,967 | false |
| kamenice zcu.pdf | missing | n/a | n/a | n/a |
| bykev_2-výkres základního členění.pdf | raw_polygons | 1,712 | 1,712 | false |
| bykev_3-hlavní výkres.pdf | raw_polygons | 4,832 | 4,832 | false |
| A_PV___KAMENICE___538299___UZ_9_15___HLV.pdf | merged_polygons | 56,642 | 1,265 | true |
| A_PV___MUKAROV___538523___UZ_2___HLV.pdf | merged_polygons | 34,828 | 2,167 | true |
| A_PV___STRUHAROV___538825___UZ_2___ZCU.pdf | raw_polygons | 4,925 | 4,925 | false |

Automated test/build status:

- backend: 37 passed
- frontend typecheck: passed
- frontend tests: 6 passed
- frontend production build: passed

Live UI smoke status on `http://127.0.0.1:4100/`:

- `scripts/smoke_webapp.py`: passed, screenshot `docs/webapp-smoke.png`
- `scripts/smoke_pdf_uploads.py`: passed for Bykev HLV, Ricany HLV, and Kamenice HLV, screenshots under `docs/ui_upload_smokes/`
- `scripts/smoke_kamenice_legend_ui.py`: passed, screenshots `docs/kamenice-v6-legend-default.png`, `docs/kamenice-v6-legend-focused-vector-defs.png`, `docs/kamenice-v6-plan-off-vector-only.png`, `docs/kamenice-v6-artifact-diagnostics.png`, and `docs/kamenice-v6-selected-polygon-proposal.png`

## UI Traceability

The UI now exposes:

- primary extraction mode and raw-fragment count
- tessellation metrics
- merge statistics
- pipeline steps including region separation, tessellation detection, merge, visual quality gate, legend autocrop, legend row extraction, spatial association, and manual crop fallback
- legend crop artifact path and bbox
- legend crop image artifact URL and page-to-image transform metadata
- top-level `UP` / `Legend` visual tabs
- selectable legend items with checkboxes separate from review/export state
- legend symbol overlays for `stav_stabil` and `navrh`
- vector definition rows filtered by the focused legend item
- legend rows and review status
- legend items, legend symbols, fake agent proposals, and missing-symbol correction tasks
- task stats, correction tasks, raw fragment debug samples, and structured errors

## V6 Legend UX Revalidation

### Baseline Before V6 Edits

- UI was running on `http://127.0.0.1:4100/`.
- Backend was still running on `http://127.0.0.1:8787/`; `4101` was not running.
- Frontend proxy defaults still pointed `/api` and `/artifacts` to `8787`.
- Browser baseline screenshot: `docs/kamenice-v6-before-legend-overloaded.png`.
- Browser console/page errors during baseline: none.
- Kamenice baseline remained extraction-correct: `merged_polygons`, 56,642 raw fragments, 1,265 primary merged polygons, tessellation score 0.7435.
- Legend baseline counts: 12 crops, 10 legend items, 20 symbols, 16 legend-linked vector definitions, 6 two-row splits, 4 missing expected symbols, checkbox-to-vector-def wiring count 10.
- UI problems visible in the baseline: dense row overlays, status text over the crop, repeated symbol badges, checkbox/focus/review/export state presented too close together, and weak bottom-table context.

### Backend Port

- Active default backend port is now `127.0.0.1:4101`.
- Frontend remains `127.0.0.1:4100`.
- `scripts/validate_kamenice_visual_artifacts.py` checks `/api/health` on `4101` and scans active defaults for `8787`; result: no active default hits.
- Final live port check: `4100` and `4101` listening; `8787` not listening.

### Legend Workbench Layout

The Legend tab now uses a controlled workbench:

- left: crop viewer with zoom out, zoom in, fit width, pan/scroll, and overlay toggles for rows, symbols, selected-only, and labels;
- right: selected legend item inspector plus compact legend item list/table;
- bottom: Vector Definitions tab auto-activates and pins the focused legend item rows.

Default overlay behavior is intentionally quiet: row outlines and a small left status marker only. Symbol overlays are off by default; when enabled, `1` and `2` badges are small, outlined, and pointer-pass-through. Review text is in the inspector/list/header, not over the legend label text.

### State Separation

- Focus: current inspected item; click/keyboard focus activates Vector Definitions only.
- Checked: worklist checkbox only; it does not change review status.
- Review: explicit `unreviewed`, `requires_review`, `approved`, `rejected`, or `conflict_requires_review`.
- Export eligibility: computed. In the UI it becomes true only when the item is checked, explicitly approved, and has no missing expected symbol. Backend export eligibility remains false until durable reviewed mappings exist.

The V6 smoke verified that focusing BU leaves review `unreviewed`, checking BU leaves review `unreviewed`, approving changes review to `approved`, rejecting changes review to `rejected`, and export eligibility follows the computed rule.

### Legend Item Mapping

For a normal selected item, the UI shows:

- expected rows: `1 STAV/STABIL`, `2 NAVRH`;
- found/missing count;
- linked vector definition rows without image thumbnails;
- legend ids: `legend_item_id`, `legend_row_id`, `legend_crop_id`, `legend_symbol_id`, `symbol_order`, `symbol_bbox_page_pt`, and `source_rect_index`.

Kamenice BU validates as found 2 / missing 0. BH validates as found 1 / missing 1; the missing NAVRH symbol is a review record, not a fabricated vector definition row. Third/fourth symbol handling remains represented as ignored/unsupported; current Kamenice target rows have ignored extras count 0.

### Multi-Column Handling

Backend rows/items/symbols carry `legend_column_index`, `legend_row_index_in_column`, crop-local image coordinates, page coordinates, and row order. The current Kamenice target legend resolves to one target column, and the UI displays `Column 1`. The crop switcher supports multiple crop artifacts when present.

### V5 Visual Artifact Continuation

- Fragment roles: tessellated area 56,464; area fill 73; legend symbol 71; unknown 34.
- White fill fragments: 0 for Kamenice; trusted white/background output: 0.
- Rectangular holes: 18; area ratio 0.000007; kept 702 holes; hole review required 0.
- Needles/spikes: max spike score 0.5957, needle count 0, sliver component count 1, thin corridor count 8, artifact review feature count 1.
- Selected polygon panel now shows raw immutable fields, proposed fields, classification reason, matched legend/vector ids, artifact flags, and export blocking reason. Example probe: raw `UNMAPPED`, proposed `RI`, reason `matched nearby target text RI`, block `matched legend item has missing expected STAV/NAVRH symbol`.
- `Plan` is truthful for Kamenice: no raster is available, so the Plan checkbox is disabled and the top status reads `Plan off (no raster)`.

The fragment-role gate changed two non-Kamenice merged outputs by one polygon while preserving validation: Světice 369 -> 368 because 10 text masks and 201 hatch fragments are excluded from trusted merge input; Mukařov 2168 -> 2167 because 12 text masks are excluded. These are recorded as artifact-role exclusions, not silent visual hiding.

### V6 Validation Results

- Backend tests: `37 passed`.
- Frontend typecheck: passed.
- Frontend tests: `6 passed`.
- Frontend production build: passed.
- `scripts/validate_kamenice_hlv.py`: passed.
- `scripts/validate_kamenice_visual_artifacts.py`: passed; output `docs/kamenice_visual_artifacts_validation.json`.
- `scripts/validate_pdf_corpus.py`: 8 present PDFs passed; `kamenice zcu.pdf` remains missing at `/mnt/c/Users/Me/Downloads/kamenice zcu.pdf`.
- `scripts/smoke_webapp.py`: passed.
- `scripts/smoke_pdf_uploads.py`: passed.
- `scripts/smoke_kamenice_legend_ui.py`: passed.

### Remaining Limitations

- Kamenice has one target legend column in the detected crop, so multi-column support is represented and wired but not proven against a multi-column target legend in this file.
- Manual legend crop save records the operator request and metadata; render-on-save still requires durable run storage.
- Backend export eligibility remains conservative and false until reviewed mappings are persisted beyond the in-session UI state.

## V7 Human Review and Legend Completion

### Why V6 Still Failed

V6 fixed the raw-fragment false success and made the legend review states visible, but screenshots still showed human-review problems:

| screenshot | defect | likely cause | task id | acceptance check |
| --- | --- | --- | --- | --- |
| `docs/kamenice-v7-baseline-up-current.png` | Kamenice Plan was unavailable and polygons were largely grey/unclassified | UI only knew the bundled Květnice raster; PDF pages were not rendered as Plan backdrops | B1/B2/D1 | Kamenice exposes `plan_snapshot_url`, Plan source `pdf_page_render`, and Source colors mode |
| `docs/kamenice-v7-baseline-artifact-current.png` | voids/spikes were visible but not actionable enough | diagnostics existed, but empty triangular/small voids were not separately counted or tied to selected feature review | C1/C2/C3 | FID 329 diagnostic is reproducible and flagged review-only with void metrics |
| `docs/kamenice-v7-baseline-legend-current.png` | legend default crop was not Fit All and labels displayed raw garbled text | V6 used Fit Width and showed `label_text_raw` as the main label | F1/F4/F7 | default zoom is Fit All; garbled raw label is not the display label |
| `docs/kvetnice-v7-baseline-legend-current.png` | default sample Legend looked like an empty failed crop workflow | sample is GeoJSON-only and has no source PDF crop artifact | E1/H5 | Legend tab shows an explicit GeoJSON-only unavailable reason and no empty crop buttons |

### Original Plan Rendering

Implemented `pymupdf_page_render_snapshot_v1`.

- Kamenice now writes `docs/plan_snapshots/collection-76c48f91822e_page_0001.png`.
- Collection fields include `plan_snapshot_available`, `plan_snapshot_url`, `plan_snapshot_source = pdf_page_render`, `plan_snapshot_page_number`, `plan_snapshot_scale`, and `plan_snapshot_transform`.
- The transform records page width/height in points, image width/height in pixels, page-to-image scale/offset, image-to-page scale/offset, and y-axis direction.
- UI status now separates `Plan`, `Plan source`, `Polygons`, `Raster validation`, and `Raw debug`.

Screenshots:

- `docs/kamenice-v7-plan-source-colors.png`
- `docs/kamenice-v7-plan-snapshot-on.png`

### FID 329 Diagnosis

`scripts/diagnose_kamenice_feature.py --fid 329` is reproducible.

- FID: 329, feature id `merged-00329`
- bbox: `[1302.64, 1777.8, 1681.36, 1966.44]`
- area: `40434.895`, perimeter: `2103.45`
- holes: 46 reported by geometry; 45 non-zero-area void rings in cleanup summary
- source style: fill `#ff0000`, stroke `#ff0000`, style group `merged-group-ed5a76e585`
- matched evidence: nearby text `SV`, matched legend item `legend-item-bc68e7ce14`, vector def `legend-vector-def-0013`
- proposed class: `SV`
- display color: `#ff0000`, source `source_style`
- artifact flags: `artifact_requires_review`, `void_artifact_candidate`
- voids: 21 triangular, 44 small, void ratio `0.003283`
- trust decision: `review_only`
- export block: `Blocked: geometry artifact candidate requires human review before export`

Screenshot: `docs/kamenice-v7-artifact-debug-fid329.png`.

### Void and Spike Rule

Implemented `void_artifact_review_flagging_v1`.

- Collection metrics now include `triangular_void_count`, `small_void_count`, `void_area_ratio`, `void_source_fragment_role`, `void_matches_original_plan`, `void_removed_as_artifact_count`, `void_kept_count`, and `void_requires_review_count`.
- Current Kamenice totals: 357 triangular voids, 619 small voids, 702 kept holes, void area ratio `0.055044`.
- No automatic filling is applied in V7. The rule is conservative: uncertain voids/spikes/thin corridors are flagged review-only and blocked from export.
- Cleanup fields on selected polygons include `cleanup_applied`, `geometry_cleanup_algorithm`, `geometry_cleanup_tolerance`, `geometry_cleanup_reason`, `cleanup_before_summary`, and `cleanup_after_summary`.

### Color Fidelity

Implemented `display_color_source_style_v1`.

Merged polygons now carry:

- `source_fill_hex`, `source_stroke_hex`, source opacity fields, and `source_style_group_id`
- `source_vector_def_id`, `legend_symbol_fill_hex`, `legend_symbol_stroke_hex`
- `display_fill_hex`, `display_stroke_hex`, and `display_color_source`

The map has a compact color selector:

- Source colors
- Classification colors
- Review status colors
- Artifact colors
- Neutral grey

Source colors are the default human-review mode.

### Legend UX Completion

Implemented the V7 legend workflow changes.

- Default crop view is `Fit All`.
- `Fit All` and `Fit width` are separate controls.
- Wheel/trackpad zoom changes the crop zoom state and can reset to Fit All.
- Crop buttons are left aligned and only show usable image crops; empty/debug crops are hidden from the primary row.
- Default overlays remain readable: rows on, symbols off, labels off, selected-only off, no status text over the crop.
- Row click focuses the legend item; arrow up/down changes selected row; space toggles the worklist checkbox; Enter focuses the current row.
- Checkbox/worklist, focus, review, and export eligibility remain separate.

Screenshots:

- `docs/kamenice-v7-legend-fit-all-default.png`
- `docs/kamenice-v7-legend-label-cleaned.png`
- `docs/kamenice-v7-legend-focused-vector-defs.png`

### Label Quality and Manual Correction

Implemented `legend_label_quality_gate_v1`.

- `label_text_raw` is preserved for diagnostics.
- Main UI uses `label_text_display`.
- Raw garbled text is not shown as the short label.
- Known Kamenice target codes receive review-required display proposals such as `BYDLENÍ VŠEOBECNÉ`.
- Manual label correction is exposed by `Edit label`, saved through `/api/manual/legend_label`, and recorded as a manual review record with original raw label, corrected label, operator/source, timestamp, reason, crop/row/item ids.

### Květnice Default Sample

The bundled Květnice sample is GeoJSON-only. V7 handles this truthfully:

- `sample_legend_crop_available = false`
- `legend_crop_source = unavailable_geojson_only_sample`
- `legend_unavailable_reason = Květnice bundled sample is GeoJSON-only and has no source PDF crop artifact.`
- The Legend tab shows that reason and no empty crop buttons.

Screenshot: `docs/kvetnice-v7-legend-unavailable-reason.png`.

### V7 Validation Results

- Backend tests: `39 passed`.
- Frontend typecheck: passed.
- Frontend tests: `6 passed`.
- Frontend production build: passed.
- `scripts/smoke_kamenice_legend_ui.py`: passed.
- `scripts/smoke_kvetnice_legend_sample.py`: passed.
- `scripts/validate_kamenice_hlv.py`: passed.
- `scripts/validate_kamenice_visual_artifacts.py`: passed.
- `scripts/smoke_webapp.py`: passed.
- `scripts/smoke_pdf_uploads.py`: passed.
- `scripts/validate_pdf_corpus.py`: 8 present PDFs passed; `kamenice zcu.pdf` remains missing at `/mnt/c/Users/Me/Downloads/kamenice zcu.pdf`.

Final runtime:

- UI: `http://127.0.0.1:4100`
- Backend: `http://127.0.0.1:4101`
- `8787`: not listening; active-default scan has no hits except validator/smoke guard strings.

### Remaining Limitations

- V7 does not automatically fill voids or cut spikes. That is intentional for this gate: raw/staging geometry remains immutable, and uncertain geometry is review-only with explicit export blocks.
- Kamenice still has four missing expected legend symbols. They are exposed as missing review records, not fabricated vector definition rows.
- Květnice default sample does not have a real bundled source legend crop; the UI now states this plainly instead of showing an empty legend workflow.

## V8.1 Gate Follow-up

### Root Cause

The remaining failures were not a single PDF parser crash. They were gate gaps around operator evidence:

- The UI still exposed old viewport zoom controls and page scrolling, which made the fixed console layout hard to review.
- Raster validation defaulted on for newly loaded sources, making vector QA visually noisy.
- Legend autocrop was a single selected bbox with little candidate evidence, so alternate vector PDFs could fail without explaining why.
- Geometry artifact evidence existed, but selected polygons did not expose a clear `clean / needs review / artifact blocked` decision or a review-only cleaned candidate.
- The app server path was split across commands; root `npm run dev` now runs frontend `4100` and backend `4101`.

### Implementation Approaches Recorded

- `legend_candidate_evidence_ranker_v8_1`: ranks left code cluster, global target-code cluster, right-panel density, and keyword-density candidates with score/signals/rejected reasons.
- `review_candidate_remove_small_triangular_voids_v8_1`: creates review-only cleaned candidate metadata for obvious small/triangular void artifacts; raw/staging geometry is unchanged.
- `geometry_artifact_review_flagging_v1`: keeps spike, sliver, thin corridor, void, island, component, and perimeter/area evidence as export-blocking diagnostics.
- `operator_manual_legend_crop_metadata_v1`: manual crop drawing is stored as metadata through `/api/manual/legend_crop`; no raw extraction mutation.
- `operator_console_fit_controls_v8_1`: UP and Legend views use compact `Fit Page | Fit Width | Fit Polygon` overlays; wheel zoom remains.

### UI Changes

- Header now shows `UP Layer Extractor · <source>` plus `VECTOR` / `RASTER` / `OTHER`.
- Backend request status shows `idle`, `running`, `completed`, or `failed` and disables duplicate load/upload actions.
- Full-page scroll is disabled; panes remain inside the fixed operator console.
- Raster validation is off by default and remains a session toggle.
- Old `- Zoom`, `+ Zoom`, `Fit All`, and `Fit width` legend buttons were removed.
- Manual legend crop can be drawn over the crop viewport and saved as review metadata.
- Selected polygon review now starts with `Geometry: needs review` or `Geometry: artifact blocked`, reason, evidence, and export status.

### V8.1 Kamenice Results

- Kamenice HLV remains stable: `56642` raw fragments, `1265` merged polygons.
- Legend selected candidate: `legend-candidate-left-code-cluster-0001`, score `0.99`, bbox `[63.96, 1160.04, 704.514, 2196.02]`.
- FID 329: `artifact blocked`, 46 rings, 65 artifact components, review-only cleaned candidate available.
- FID 337: `artifact blocked`, 25 rings, 36 artifact components, review-only cleaned candidate available.
- Diagnostics written:
  - `docs/kamenice_fid329_diagnostic.json`
  - `docs/kamenice_fid337_diagnostic.json`
  - `docs/kamenice_hlv_validation.json`
  - `docs/kamenice_visual_artifacts_validation.json`
  - `docs/pdf_validation_corpus.json`

Screenshots:

- `docs/kamenice-v8_1-plan-source-colors.png`
- `docs/kamenice-v8_1-plan-snapshot-on.png`
- `docs/kamenice-v8_1-artifact-debug-fid329.png`
- `docs/kamenice-v8_1-legend-fit-page-default.png`
- `docs/kamenice-v8_1-legend-label-cleaned.png`
- `docs/kamenice-v8_1-legend-focused-vector-defs.png`
- `docs/kamenice-v8_1-manual-legend-crop.png`

### V8.1 Validation Results

- Backend tests: `39 passed`.
- Frontend typecheck: passed.
- Frontend tests: `6 passed`.
- Frontend production build: passed.
- `scripts/validate_kamenice_hlv.py`: passed.
- `scripts/diagnose_kamenice_feature.py --fid 329`: passed.
- `scripts/diagnose_kamenice_feature.py --fid 337`: passed.
- `scripts/smoke_kamenice_legend_ui.py`: passed.
- `scripts/validate_kamenice_visual_artifacts.py`: passed.
- `scripts/smoke_kvetnice_legend_sample.py`: passed.
- `scripts/smoke_webapp.py`: passed.
- `scripts/smoke_pdf_uploads.py`: passed.
- `scripts/validate_pdf_corpus.py`: 8 present PDFs passed; `kamenice zcu.pdf` is still missing at `/mnt/c/Users/Me/Downloads/kamenice zcu.pdf`.

Final runtime:

- UI: `http://127.0.0.1:4100`
- Backend: `http://127.0.0.1:4101`
- `8787`: not listening; active-default scan passed.

## V8.2 Gate Follow-up

### Root Cause

V8.1 correctly stopped the raw-fragment false success and kept Kamenice stable at `56642` raw fragments and `1265` merged polygons, but the remaining hatch/dotted-boundary issue is semantic, not just geometric.

- The white hatch/grid visible inside red change areas is not emitted as a clean independent white line layer in this PDF; after tessellation merge it appears mainly as tiny interior rings/holes.
- The dotted black boundary and thick dark boundaries are present as vector evidence, but not as a reliable closed split graph.
- Because the hatch, dotted boundary, thick boundary, text anchor, and legend evidence disagree about where a clean automatic cut should occur, the extractor must block clean export and mark manual split/review instead of silently merging different planning semantics.

### Implementation Approaches Recorded

- `review_candidate_remove_label_mask_white_background_hatch_grid_holes_v8_2`: classifies polygon holes as hatch-grid artifacts, white-background artifacts, real planning voids, or review-required unknown holes. Only candidate/review geometry removes eligible artifacts; raw geometry remains preserved.
- `method_aware_extraction_profile_v8_2`: records fill style polygonization, hatch segmentation, dotted boundary segmentation, thick boundary segmentation, text anchor assignment, legend mapping, raster-assisted review, and manual-split gating.
- `hatch_dotted_boundary_manual_split_gate_v8_2`: blocks export when hatch/dotted/thick boundary evidence exists but cannot produce a reliable vector-only semantic split.
- `operator_extraction_profile_tab_v8_2`: exposes Method, Czech explanation, Status, Success rate, Used for candidate, Main evidence, and Main risk in the bottom `Extraction` tab.
- `operator_zoom_and_label_controls_v8_2`: adds 10 UP zoom steps through Max (`1600x` internal scale), wheel zoom, and a selected-polygon label toggle.

### UI Changes

- Removed the visible top `Legend Workbench` header.
- Legend now starts with compact status/control rows: `Legend crop source`, `Candidate`, and `Confidence`.
- Legend unavailable state is compact and preserves Květnice GeoJSON-only truth.
- Legend crop wheel zoom and pan both work; normal filter controls no longer have boxed borders.
- The bottom/details panel has an `Extraction` tab for method-level evidence.
- UP view has `Fit Page | Fit Width | Fit Polygon` plus 10 zoom steps: `25%`, `50%`, `100%`, `200%`, `400%`, `800%`, `1600%`, `3200%`, `6400%`, `Max`.
- `Selected label` is on by default and is smaller than the previous selected popup.
- Bottom/review splitters remain simple 1px light-grey resize lines with no layout gap.

### V8.2 Kamenice Results

- Raw fragments: `56642`.
- Merged polygons: `1265`.
- Hatch candidates: `635` hatch-grid interior-ring artifacts.
- Dotted-boundary candidates: `83`.
- Thick-boundary candidates: `9`.
- Manual split required: `875` text/class-anchored polygons.
- Export blocked: `1265` polygons until review/manual semantic split.
- Hole cleanup diagnostics: `638` holes removable only in review candidate geometry, `47` unknown holes still review-required.
- FID diagnostics refreshed: `329`, `337`, and `353` all found and carry hole cleanup/manual split fields.

Diagnostics written:

- `docs/kamenice_fid329_diagnostic.json`
- `docs/kamenice_fid337_diagnostic.json`
- `docs/kamenice_fid353_diagnostic.json`
- `docs/kamenice_hole_cleanup_diagnostic.json`
- `docs/kamenice_hatch_split_diagnostic.json`
- `docs/kamenice_hlv_validation.json`
- `docs/kamenice_visual_artifacts_validation.json`
- `docs/pdf_validation_corpus.json`

Screenshots:

- `docs/kamenice-v8_2-up-zoom-steps-selected-label.png`
- `docs/kamenice-v8_2-legend-compact-candidate-status.png`
- `docs/kamenice-v8_2-extraction-method-profile.png`

### V8.2 Validation Results

- Backend tests: `39 passed` using `.venv/bin/python -m pytest backend/tests -s`.
- Frontend typecheck: passed.
- Frontend tests: `6 passed`.
- Frontend production build: passed.
- Python compile checks: passed.
- `scripts/validate_kamenice_hlv.py`: passed.
- `scripts/smoke_kamenice_legend_ui.py`: passed.
- `scripts/validate_kamenice_visual_artifacts.py`: passed.
- `scripts/smoke_kvetnice_legend_sample.py`: passed.
- `scripts/smoke_webapp.py`: passed.
- `scripts/smoke_pdf_uploads.py`: passed for Bykev, Ricany, and Kamenice uploads.
- `scripts/validate_pdf_corpus.py`: 8 present PDFs passed with `completed_review_blocked`; `kamenice zcu.pdf` is still missing at `/mnt/c/Users/Me/Downloads/kamenice zcu.pdf`.

Final runtime:

- UI: `http://127.0.0.1:4100`
- Backend: `http://127.0.0.1:4101`
- `8787`: active-default scan passed.

## V8.3.1 First-Principles Algorithm Lab

### Baseline Revalidation

V8.3.1 revalidated the Kamenice HLV baseline before changing the algorithm path:

- Raw fragments: `56642`.
- Merged polygons: `1265`.
- Geometry errors: `840`.
- Export blocked: `1265`.
- Manual split required: `875`.
- Hatch candidates: `635`.
- Dotted-boundary candidates: `83`.
- Thick-boundary candidates: `9`.
- FIDs `329`, `337`, and `353`: all found.

### First-Principles Result

The target object is a planning-semantic polygon, not a same-fill-color polygon. The evidence split is now explicit:

- Fill color creates candidate regions but cannot prove semantic boundaries.
- Hatch/grid evidence can define a subtype or subregion, but Kamenice exposes it mainly through raster evidence and post-merge hatch/grid holes.
- Dotted and thick black boundaries support a split, but the detected graph is not closed enough for automatic export geometry.
- Text anchors such as `BX.p` and `Z.51a` validate/rank candidates; they do not create geometry by themselves.
- Legend mapping validates style semantics; it cannot split same-fill regions alone.
- Raster evidence can support review candidates, but it does not silently replace vector truth.
- Manual split remains required where automatic split evidence is incomplete.

### Implementation Approaches Recorded

- `vector_evidence_index_v8_3_1`: preserves pre-merge path/text evidence with bbox, drawing operation, fill/stroke, stroke width, dash pattern, opacity, open/closed state, z-order, and likely role.
- `vector_hatch_line_premerge_index`: tested white hatch/grid isolation before merge; rejected for Kamenice because the target hatch is not exposed as a clean standalone vector hatch layer.
- `raster_hatch_grid_segmentation`: renders a 144 DPI ROI and records a hatch/grid envelope diagnostic; kept as supporting evidence only.
- `dotted_boundary_reconstruction`: records vector/raster dark-dot evidence and a near-loop diagnostic; combined into review scoring, not export geometry.
- `thick_boundary_segmentation`: records thick dark boundary candidates as barrier evidence; combined into review scoring.
- `text_anchor_constrained_assignment`: attaches labels as constraints and explicitly prevents text-only splitting.
- `hybrid_graph_constrained_polygonization`: combines hatch, dotted/thick boundary, text, legend, and geometry-validity signals into one review-only candidate.
- `manual_split_fallback_schema`: emits a first-class `manual_semantic_split` payload while keeping raw geometry immutable.
- `synthetic_controls_and_regression_tests`: adds isolated tests for hatch, dotted boundary, thick boundary, text-only assignment, label-mask cleanup, and real-void preservation.

### Target ROI And Evidence

- Target: `Kamenice BX.p Z.51a hatch/dotted split`.
- ROI source: derived from FID bbox.
- ROI bbox: `[1222.64, 1364.2, 2014.2, 2046.44]`.
- Target labels found in the ROI include `Z.51a`, `BX.p`, and neighboring/conflicting `BX.c` labels.
- Vector evidence summary: `157834` records, `38269` fills, `156350` strokes, `7583` red fills, `2990` near-white strokes, `67101` near-black strokes, `281` hatch-line candidates, `247` label-mask candidates, and `270` text anchors.
- The broad pre-index dot candidate count is intentionally noisy (`66070`) because small dark glyphs/blobs are retained as evidence; the method profile still uses the narrower dotted-boundary count (`83`) for review gating.

### Experiment Outcomes

| ID | Approach | Status | Score | Keep/reject | Result |
| --- | --- | ---: | ---: | --- | --- |
| E01 | Vector hatch line premerge detection | failed | `0.00` | reject | Kamenice does not expose target hatch as usable standalone white vector strokes. |
| E02 | Raster hatch/grid segmentation | partial | `0.62` | combine | Hatch/grid region detected in the ROI; false-positive risk remains medium. |
| E03 | Dotted boundary reconstruction | partial | `0.55` | combine | Boundary evidence exists, but closure is not reliable enough for export geometry. |
| E04 | Thick boundary segmentation | partial | `0.45` | combine | Thick boundary evidence supports the split hypothesis but does not close the graph. |
| E05 | Text-anchor constrained assignment | partial | `0.35` | combine | `BX.p` / `Z.51a` labels validate the candidate but cannot split it. |
| E06 | Hybrid graph / constrained polygonization | review required | `0.80` | combine | Produces one review-only candidate backed by hatch, boundary, and text evidence. |
| E07 | Manual split fallback schema | success | `1.00` | keep | Manual semantic split payload is available and linked to the target ROI evidence. |
| E08 | Synthetic controls and regression tests | success | `1.00` | keep | Synthetic controls pass for hatch, dotted, thick, text, label mask, and real void behavior. |

Best current method: `E06 hybrid graph review-only candidate + E07 manual split fallback`.

### Candidate Split Status

V8.3.1 creates one `experiment_candidate_geometry` for the Kamenice target ROI. It is visible in the UP preview as a review-only overlay and listed in the Extraction tab experiment rows. It is not exportable:

- `raw_preserved`: true.
- `export_eligible`: false.
- Kamenice export status: `blocked`.
- Required next action: operator reviews the ROI candidate and records `manual_semantic_split` child geometries if accepted.

### Reports And Artifacts

- Ledger: `docs/extraction_experiments/KAMENICE_HLV_V8_3_EXPERIMENT_LEDGER.md`.
- Experiment JSON: `docs/extraction_experiments/kamenice_v8_3_experiment_results.json`.
- Target case JSON: `docs/extraction_experiments/kamenice_target_case_v8_3.json`.
- Vector evidence summary: `docs/extraction_experiments/kamenice_vector_evidence_index_summary.json`.
- Target validation: `docs/extraction_experiments/kamenice_target_case_validation.json`.
- Raster hatch diagnostic: `docs/extraction_experiments/kamenice_e02_raster_hatch_diagnostic.json`.
- Raster hatch overlay: `docs/extraction_experiments/kamenice_e02_raster_hatch_overlay.png`.
- Dotted-boundary diagnostic: `docs/extraction_experiments/kamenice_e03_dotted_boundary_diagnostic.json`.
- Dotted-boundary overlay: `docs/extraction_experiments/kamenice_e03_dotted_boundary_overlay.png`.
- UI screenshots remain under `docs/kamenice-v8_1-*`, `docs/kamenice-v8_2-*`, `docs/webapp-smoke.png`, and `docs/ui_upload_smokes/`.

### V8.3.1 Validation Results

- Backend tests: `45 passed` using `.venv/bin/python -m pytest backend/tests -s`.
- Frontend typecheck: passed.
- Frontend tests: `6 passed`.
- Frontend production build: passed.
- `scripts/run_kamenice_v8_3_experiments.py`: passed and wrote the experiment ledger/artifacts.
- `scripts/validate_kamenice_target_case.py`: passed with one review-only experiment candidate.
- `scripts/validate_kamenice_hlv.py`: passed with E01-E08 present and algorithm lab diagnostics attached.
- `scripts/validate_kamenice_visual_artifacts.py`: passed; `4101` health check passed and active-default `8787` scan was clean.
- `scripts/smoke_kamenice_legend_ui.py`: passed; Extraction tab shows E01-E08 and the candidate split overlay.
- `scripts/smoke_kvetnice_legend_sample.py`: passed.
- `scripts/smoke_webapp.py`: passed.
- `scripts/smoke_pdf_uploads.py`: passed for Bykev, Ricany, and Kamenice uploads.
- `scripts/validate_pdf_corpus.py`: 8 present PDFs passed as `completed_review_blocked`; `kamenice zcu.pdf` remains missing at `/mnt/c/Users/Me/Downloads/kamenice zcu.pdf`.
- Corpus experiment-candidate reporting is scoped: only `A_PV___KAMENICE___538299___UZ_9_15___HLV.pdf` reports `experiment_candidate_available_count = 1`; all non-Kamenice PDFs report `0`.

Final V8.3.1 decision: the Kamenice target case is not clean-exportable. The correct fixed behavior is a visible, review-only candidate supported by multiple evidence signals, plus explicit manual split fallback and export blocking.
