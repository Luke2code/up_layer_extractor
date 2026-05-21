# Vector PDF Extraction Fix Report

Date: 2026-05-18

## Root Cause

The backend correctly diagnosed the supplied PDFs as vector fill candidates, but `extract_vector_candidates` only emitted features for PyMuPDF rectangle path items (`re`). Most municipal planning PDFs in the validation set encode filled areas as general path operations:

- `l`: line segments
- `c`: cubic Bezier curves
- `qu`: quadrilaterals

That made the algorithm route to `vector_fill_style_polygon_v1` and then return either zero polygons or only small rectangle fragments.

The UI also assumed the Kvetnice page size and background image for every collection, so extracted PDFs with different dimensions could render off-scale or over the wrong plan image.

## Implementation Approaches / Algorithms

1. Existing rectangle-only vector fill extraction
   - Scope: `re` items only.
   - Result: kept as a compatible path, but insufficient for the attached vector PDFs.

2. General filled-path polygonization
   - Converts `l`, `c`, `qu`, and `re` drawing items into closed rings.
   - Cubic curves are flattened into bounded line segments.
   - Disconnected subpaths are split into independent rings.
   - Degenerate or zero-area rings are rejected.

3. Compound path / hole grouping
   - Uses ring containment depth to group odd-depth rings as holes under even-depth outer rings.
   - Output remains GeoJSON `Polygon`; no `MultiPolygon` is emitted.
   - If grouped holes cancel the outer area, the extractor falls back to the positive-area outer ring instead of emitting invalid geometry.

4. Candidate diagnostics
   - Adds extraction stats for filled drawings seen, empty filled drawings, path polygons, rectangle polygons, curve items flattened, and background rings skipped.
   - Preserves raw drawing style evidence in `raw_objects`.

5. UI page-coordinate rendering fix
   - Map preview now uses each collection's `page_width_pt` and `page_height_pt`.
   - The Kvetnice plan image is only shown for the Kvetnice sample.
   - Candidate fills use the source fill color when semantic class mapping is still `UNMAPPED`.
   - Polygons with holes render with `fillRule="evenodd"`.
   - Very large collections keep the full FeatureCollection but disable the duplicate validation overlay by default, avoid empty label DOM, and skip the backend definition roundtrip to prevent browser stalls.

## Validation Results

All runs used `vector_fill_style_polygon_v1`. Every feature was validated as:

- geometry type `Polygon`;
- closed exterior ring;
- positive area;
- no `MultiPolygon`.

| PDF | Features | Bad Type | Bad Closed | Bad Area | Holes | Runtime |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| UP__MNICHOVICE__538493__UZ_1__HLV.PDF | 2,236 | 0 | 0 | 0 | 54 | 16.50s |
| UP__SVETICE___A_PV__538841___UZ_1_HLV.pdf | 19,363 | 0 | 0 | 0 | 0 | 4.81s |
| UP_538728_RICANY_HLV.pdf | 49,967 | 0 | 0 | 0 | 5,872 | 13.58s |
| kamenice zcu.pdf | 10,920 | 0 | 0 | 0 | 2,716 | 7.78s |
| bykev_2-výkres základního členění.pdf | 1,712 | 0 | 0 | 0 | 465 | 1.32s |
| bykev_3-hlavní výkres.pdf | 4,832 | 0 | 0 | 0 | 1,175 | 3.29s |
| kamenice hlv.pdf | 56,642 | 0 | 0 | 0 | 13,425 | 15.88s |
| A_PV___MUKAROV___538523___UZ_2___HLV.pdf | 34,828 | 0 | 0 | 0 | 452 | 13.63s |
| A_PV___STRUHAROV___538825___UZ_2___ZCU.pdf | 4,925 | 0 | 0 | 0 | 899 | 5.24s |

## Regression Commands

```bash
PYTHONPATH=/mnt/c/coding/up_layer_extractor /mnt/c/coding/up_layer_extractor/.venv/bin/python -m pytest /mnt/c/coding/up_layer_extractor/backend/tests -q -s
```

Result: `21 passed`.

```bash
cd /mnt/c/coding/up_layer_extractor/frontend
npm run typecheck
npm test -- --run
npm run build
```

Results:

- TypeScript: passed.
- Vitest: `2 passed (2)`, `6 passed (6)`.
- Vite production build: passed.

```bash
python3 /mnt/c/Users/Me/.codex/skills/webapp-testing/scripts/with_server.py \
  --server "bash -lc 'PYTHONPATH=/mnt/c/coding/up_layer_extractor /mnt/c/coding/up_layer_extractor/.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 4101'" --port 4101 \
  --server "bash -lc 'cd /mnt/c/coding/up_layer_extractor/frontend && npm run dev -- --host 127.0.0.1 --port 4100 --strictPort'" --port 4100 \
  --timeout 90 -- /mnt/c/coding/up_layer_extractor/.venv/bin/python /mnt/c/coding/up_layer_extractor/scripts/smoke_webapp.py
```

Result: webapp smoke passed with no browser console errors.

Additional upload smoke:

- Uploaded `bykev_2-výkres základního členění.pdf`.
- UI showed `1712 upload candidates`.
- Diagnostics displayed the PDF page width `2525.669921875`.
- No browser console or page errors were raised.
- Screenshot: `/mnt/c/coding/up_layer_extractor/docs/webapp-bykev-upload.png`

Large upload smoke:

- Uploaded `UP_538728_RICANY_HLV.pdf`.
- UI showed `49967 upload candidates`.
- Diagnostics displayed the PDF page width `5051.33984375`.
- No browser console or page errors were raised.
- Screenshot: `/mnt/c/coding/up_layer_extractor/docs/webapp-ricany-upload.png`

Note: the venv console script shebang points to an older Downloads path, so validation uses the venv Python executable directly.
