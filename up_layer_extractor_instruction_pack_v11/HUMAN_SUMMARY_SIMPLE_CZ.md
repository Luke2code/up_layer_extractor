# Přehled pro člověka — jednoduše česky

## Co nástroj dělá

`up_layer_extractor` bere územně-plánovací PDF výkres a snaží se z něj vytáhnout plochy jako polygony.

Výsledek nejsou hned finální GIS data. Nejdřív vzniknou kandidáti, které může člověk zkontrolovat a opravit.

## Hlavní tok

```text
PDF → raw vector import → definice stylů/legendy → kandidátní polygony → ruční kontrola → schválený výstup
```

## Důležité tabulky

### `up_import.vector_import`

Surový výpis kresby z PDF.

Sem patří: fill, line, dash, bbox, path ops, geometrie. Ještě žádná business klasifikace.

### `up_import.vector_def`

Definice stylu z legendy.

Příklad: červená výplň znamená `RZVP / BI / STAV`.

### `up_import.up_text_def`

Definice textových labelů.

Příklad: text `Z11` nebo `P2/01` je změnový label.

### `up_stg.vector_stg_*`

Pracovní kandidáti algoritmu.

Sem patří rozpad na single polygon, přiřazení textů, residual/missing/extra kontrola.

### `up_manual`

Ruční zásahy člověka.

Sem patří oprava hranice polygonu, poznámka, label, schválení nebo zamítnutí.

### `up_core.vector_output`

Finální schválené polygony.

Pouze tady je výstup, kterému aplikace smí věřit.

## Nové funkce ve v9

### Ruční úprava hranice polygonu

Člověk může vybrat polygon a upravit jeho hranici.

Důležité: surová extrakce se nepřepíše. Oprava se uloží zvlášť jako manual correction.

### Labely a poznámky

Ke každému polygonu lze přidat:
- label
- poznámku
- warning
- rozhodnutí reviewera

`text_id` z PDF zůstává zachovaný. Ruční label je samostatná věc.

### Automatické návrhy legendy

Nástroj se pokusí sám najít legendu a vytvořit návrhy definic stylů.

Člověk pak vybere, co daný styl skutečně znamená.

## Tvrdé pravidlo

Pokud algoritmus neví, nesmí si vymýšlet.

Lepší výsledek je:

```text
review_required
```

než falešně správný polygon.


## v10 — vlastní přemapování tříd

Nově přibývá konfigurovatelné přemapování `LAYER / CLASS / TYPE`.

Jednoduše:
- extractor nejdřív zjistí surový styl, text a legendu,
- potom navrhne, co to znamená (`RZVP.BI`, `ZMEN.Z`, `SV.2`, atd.),
- člověk může návrh potvrdit nebo opravit,
- finální výstup jde až po schválení do `up_core.vector_output`.

Důležité: když systém neví, nesmí si vymýšlet. Musí označit `UNMAPPED` / `review_required`.
