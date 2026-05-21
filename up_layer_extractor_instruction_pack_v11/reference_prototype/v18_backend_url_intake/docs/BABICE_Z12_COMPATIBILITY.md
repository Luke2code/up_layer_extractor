# Babice Z12 compatibility test

## Test URL

`https://cdn.prod.website-files.com/646b8908bd5c653189d58ca8/686bfa78787ed82741153c7a_02_%C3%9AP%20Babice_%C3%9APLN%C3%89%20ZN%C4%9AN%C3%8D%20po%20Z12_Hlavn%C3%AD%20v%C3%BDkres.pdf`

## V18 additions

- Server-side PDF URL intake so browser CORS does not block extraction.
- Percent-safe Czech URL handling.
- Backend endpoint: `POST /api/extract` with JSON body `{ "url": "...pdf" }`.
- Upload endpoint fallback: `POST /api/extract_upload`.
- Babice profile stub in `profiles/babice_z12_profile.yaml`.
- Preview can call local backend `http://127.0.0.1:8787/api/extract`.

## Validated here

- Exact Babice URL parsing/normalization.
- Backend Python syntax/import.
- URL encoded path preservation.
- Existing Květnice GeoJSON/data model remains valid.
- Preview JavaScript remains valid.

## Not fully validated here

This environment could not resolve `cdn.prod.website-files.com`, so the actual Babice PDF bytes could not be downloaded here. That means final Babice geometry extraction is not honestly validated in this session. Run the backend locally/Codex, or upload the PDF file manually.

## Local validation

```bash
cd up_layer_extractor_rebuild_pack_v18
./scripts/run_backend.sh
```

Then open the V18 preview and paste the Babice URL, or call:

```bash
curl -X POST http://127.0.0.1:8787/api/extract \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://cdn.prod.website-files.com/646b8908bd5c653189d58ca8/686bfa78787ed82741153c7a_02_%C3%9AP%20Babice_%C3%9APLN%C3%89%20ZN%C4%9AN%C3%8D%20po%20Z12_Hlavn%C3%AD%20v%C3%BDkres.pdf"}' \
  > babice_candidates.geojson
```

## Rule

Do not copy Květnice style/color mappings into Babice. Babice must learn its own legend/style mapping.
