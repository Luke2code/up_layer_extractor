# Pack validation report V18

## Status
`passed_with_conditions`

## Scope
V18 adds Babice Z12 remote-PDF URL support and backend extraction intake while preserving the V17 polygon extraction data/model.

## Validations run

- Preview JavaScript syntax: `node --check validation/v18_preview_script.js` - passed.
- Backend Python syntax: `py_compile backend/up_layer_extractor_service.py` - passed.
- Babice URL normalization test - passed.
- `TYPE_CODE` contract test: `STAV=1`, `NAVRH=2` - passed.
- V17 Květnice GeoJSON retained - passed by unchanged sample data.

## Babice URL handling

Exact URL fixture:

`https://cdn.prod.website-files.com/646b8908bd5c653189d58ca8/686bfa78787ed82741153c7a_02_%C3%9AP%20Babice_%C3%9APLN%C3%89%20ZN%C4%9AN%C3%8D%20po%20Z12_Hlavn%C3%AD%20v%C3%BDkres.pdf`

Validation confirms:

- URL remains HTTPS.
- URL remains `.pdf`.
- Czech/percent-encoded path segments are preserved.
- Preview includes `Use Babice Z12 URL` button.
- Preview includes `Extract PDF via backend` button.
- Backend endpoint accepts PDF URL via `POST /api/extract`.

## Important condition

The actual Babice PDF could not be downloaded in this environment because DNS resolution for `cdn.prod.website-files.com` failed. Therefore the pack is URL-ready/backend-ready, but Babice geometry extraction must be validated locally/Codex or by uploading the PDF file.

## No changes

- Květnice polygon extraction logic was not changed.
- V17/V16 preview UI logic was preserved except for backend PDF intake additions.
- No Babice classification mapping was faked.
