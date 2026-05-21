# Jednoduché shrnutí pro člověka — V17

## Co nástroj dělá
Nástroj ukazuje polygony vytažené z PDF územního plánu. U každého polygonu drží základní atributy:
`FID`, `LAYER`, `CLASS`, `TYPE`, `LAYER_CLASS`, `class_type`, `text_id`, `IS_CLOSED`.

## Důležité pojmy
- `LAYER=RZVP` = plocha s rozdílným způsobem využití.
- `LAYER=ZMEN` = změnová plocha (`Z` zastavitelná, `P` přestavba).
- `CLASS` = kategorie, např. `BI`, `SV`, `SK`, `RN`, `Z`, `P`.
- `TYPE=STAV` = stabilizovaná plocha.
- `TYPE=NAVRH` = návrhová plocha / plocha změny.
- `class_type` = zkratka: `BI.1` znamená `BI/STAV`, `BI.2` znamená `BI/NAVRH`.

## Co bylo opraveno
- Popisek v mapě už není automaticky `FID`; `text_id`, `FID` a `CLASS` jsou samostatné label vrstvy.
- Popup je menší a čistší; nezobrazuje `null` hodnoty.
- Raster validation reaguje na přesnou kombinaci filtrů `LAYER / CLASS / TYPE`.
- Filtry jsou dependentní: když změním `LAYER`, ukáže se jen použitelná `CLASS`; když změním `CLASS`, ukáže se jen použitelný `TYPE`.
- Klávesa `ESC` zruší výběr.
- Do preview lze nahrát jiný GeoJSON. PDF se musí nejdřív zpracovat backend extraktorem.

## Omezení
Není to univerzální kouzelná PDF čtečka. Funguje dobře pro vektorová PDF s čitelnými styly/legendou. Pokud je PDF rastrové, špatně stylované, bez legendy nebo se silným překryvem, je potřeba jiný postup nebo ruční review.

---

## V18 - Babice URL a jiné PDF odkazy

Nástroj nově počítá s tím, že uživatel vloží přímo URL na PDF, například hlavní výkres Babice po Z12.

Pro PDF z internetu nestačí čistý HTML preview. Prohlížeč často narazí na CORS nebo neumí bezpečně číst PDF vektorová data. Správný model je backend:

- uživatel vloží URL,
- backend PDF stáhne,
- backend ověří, že PDF obsahuje vektorové kresby,
- backend vyrobí GeoJSON kandidáty,
- preview zobrazí výsledek.

Pro Babice se nesmí použít barvy z Květnice. Každé PDF může mít vlastní legendu a vlastní styly. Správný postup je: načíst Babice PDF, najít jeho legendu/styly, teprve potom mapovat `CLASS`, `TYPE`, `LAYER`.

V této relaci se Babice PDF nepodařilo stáhnout kvůli DNS/CDN problému prostředí. To není validace geometrie. Lokálně nebo v Codexu je nutné spustit backend a PDF reálně zpracovat.
