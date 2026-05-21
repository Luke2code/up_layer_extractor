# PACK VALIDATION REPORT V17

## Data checks
- total features: 112
- class_type present: 112/112
- non-Polygon features: 0
- data errors: none

## UI checks
- yellow dotted selected border requested and implemented.
- popup hides null values and removes leader line.
- popup key font: 6px grey; values semi-bold.
- separate label toggles: text_id / FID / CLASS.
- dependent filter logic kept.
- exact-filter raster validation kept.
- GeoJSON file/URL intake added; PDF intake is backend-only.

## Genericity
The logic is generic for vector PDFs with extractable vector paths and mappable legend styles. It is not generic for arbitrary raster-only PDFs.

## Syntax check
- `node --check validation/v17_preview_script.js`: passed.
