# UP Layer Extractor SSOT — V17

## Účel
Nástroj slouží k extrakci a review polygonových vrstev z vektorového PDF územního plánu. Aktuální ukázkový zdroj je Květnice.

## Datový model
Každý feature je právě jeden `Polygon`.

Povinné atributy:
- `FID` — stabilní pořadové ID v preview/exportu.
- `LAYER` — např. `RZVP` nebo `ZMEN`.
- `CLASS` — věcná třída vrstvy. Pro `RZVP`: `BI`, `RN`, `SV`, `SK`. Pro `ZMEN`: `Z`, `P`.
- `TYPE` — `STAV` nebo `NAVRH`. Pro `ZMEN` je defaultně `NAVRH`.
- `LAYER_CLASS` — vypočtené `LAYER.CLASS`, např. `RZVP.BI`.
- `class_type` — vypočtené `CLASS.1` pro `STAV`, `CLASS.2` pro `NAVRH`.
- `text_id` — popisek změny z plánu, např. `Z11`, `P2/01`; pokud neexistuje, je `null`.
- `IS_CLOSED` — boolean validace uzavření exterior ringu.

## Preview logika V17
- Plan overlay/contrast slider zůstává.
- Výběr polygonu má žlutý tenký dotted border.
- Popup neobsahuje spojovací čáru, má subtilní border, minimální rounded, světle šedé pozadí.
- Popup nezobrazuje atributy s `null` hodnotou.
- Label vrstvy jsou oddělené: `text_id`, `FID`, `CLASS`. Jejich posuny jsou rozdílné, aby nekolidovaly.
- `CLASS` filter je dependent na `LAYER`; změna `LAYER` resetuje `CLASS`, `TYPE`, výběr.
- `TYPE` filter je dependent na `LAYER + CLASS`; změna `CLASS` resetuje `TYPE`, výběr.
- `ESC` maže výběr.
- File/URL intake v browseru přijímá GeoJSON FeatureCollection. PDF URL/file se pouze zachytí; skutečnou extrakci musí udělat backend.

## Raster validation V17
Raster validation se vykresluje pouze z aktuálního filtrovaného feature setu: `LAYER / CLASS / TYPE / IS_CLOSED`.
Nepoužívá se starý broad class PNG mask, protože ignoroval `TYPE` a způsoboval multi-color bleed-through.

Význam:
- `NAVRH` = yellow hatch.
- `STAV` = blue dot/tint.
- `ZMEN` = generated-footprint QA, ne fill-source raster, protože `ZMEN` nemá fill color.

## Zakázané zkratky
- Nepředstírat EPSG/S-JTSK, pokud PDF není georeferencované.
- Nepředstírat, že `ZMEN` lze validovat přes fill color.
- Nepoužívat broad class raster mask pro type-specific validation.
- Neslučovat samostatné polygony do MultiPolygon, pokud review model vyžaduje jeden polygon na feature.

---

## V18 - Babice URL / generic remote PDF intake

The extractor must support remote PDF URLs, including URLs with Czech/unicode names and percent encoding. Example Babice URL:

`https://cdn.prod.website-files.com/646b8908bd5c653189d58ca8/686bfa78787ed82741153c7a_02_%C3%9AP%20Babice_%C3%9APLN%C3%89%20ZN%C4%9AN%C3%8D%20po%20Z12_Hlavn%C3%AD%20v%C3%BDkres.pdf`

Browser-only PDF extraction is rejected. Use backend fetch/extract:

- `POST /api/extract` for URL PDFs.
- `POST /api/extract_upload` for manual PDF uploads.
- Browser preview consumes the resulting GeoJSON.

Genericity: this is generic for vector PDFs with extractable path drawings. It is not a universal solution for raster-only/scanned PDFs. Classification remains profile/legend-dependent per document. Never reuse Květnice style colors for Babice without validating Babice legend styles.
