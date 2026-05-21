# Extraction Logic for AI Agent — V17

## 1. Intake
Accept either:
1. source PDF URL/file for backend extraction, or
2. already extracted GeoJSON FeatureCollection for browser preview.

Browser-only preview must not pretend to parse arbitrary PDF. If the input is PDF, hand it to the backend extractor pipeline.

## 2. PDF vector extraction pipeline
1. Download/open PDF.
2. Read page metadata and render page for visual review.
3. Extract vector paths/fills from PDF.
4. Detect legend styles and map styles to semantic classes.
5. Build source class candidates:
   - RZVP classes from fill styles: `BI`, `RN`, `SV`, `SK`.
   - RZVP type from legend fill/hatch semantics: `STAV`, `NAVRH`.
   - ZMEN from dotted boundaries + text labels, not fill color.
6. Polygonize each connected area.
7. Split any MultiPolygon into individual Polygon features unless the contract explicitly allows MultiPolygon.
8. Attach attributes: `FID`, `LAYER`, `CLASS`, `TYPE`, `LAYER_CLASS`, `class_type`, `text_id`, `IS_CLOSED`.

## 3. Validation
Run these checks:
- every feature geometry type is `Polygon`;
- every exterior ring is closed;
- `LAYER_CLASS = LAYER + '.' + CLASS`;
- `class_type = CLASS + '.1'` for `TYPE=STAV`, `CLASS + '.2'` for `TYPE=NAVRH`;
- `ZMEN.TYPE = NAVRH`;
- `ZMEN.has_fill_color = false`;
- no old `RZVP/RZVP_TYPE` values override the new model.

## 4. Raster validation rule
Validation layer in preview must be exact-filter-based:
`visible = FEATURES where LAYER/CLASS/TYPE/IS_CLOSED pass filters`.
Render only `visible` into validation layer.
Do not show any pre-rendered class mask that is broader than the active filter.

## 5. Residual validation for production
For robust production QA compute:
- `missing = source_candidate_union - generated_union`
- `extra = generated_union - source_candidate_union`
Fail or mark review if residual area exceeds tolerance.

For `RZVP`, `source_candidate_union` may come from fill-style raster/vector source.
For `ZMEN`, it must come from dotted boundary topology + text_id; do not use fill color.
