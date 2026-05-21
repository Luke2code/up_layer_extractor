# Schéma model — jednoduše česky

## Rozhodnutí

Ano, lepší je použít:

- `up_import`
- `up_stg`
- `up_manual`
- `up_core`
- `up_api`

Je to konzistentnější než dřívější dělení `up_source`, `up_profile`, `up_extract`, `up_review`, `up_validation`.

## Proč je to lepší

Původní názvy popisovaly technické oblasti, ale nebyl z nich jasný tok dat.

Nový model popisuje pipeline:

```text
IMPORT → STAGING → MANUAL REVIEW → CORE TRUTH → API
```

To je srozumitelné pro člověka, Codex i orchestration engine.

## Význam schémat

### `up_import`

Sem patří vše, co přichází ze zdroje a co definuje, jak zdroj číst.

Obsah:
- PDF zdroj
- stažený soubor / upload
- PDF page metadata
- `vector_import` = raw PDF drawings extract
- `vector_def` = definice stylu vektorů podle legendy
- `up_text_def` = definice textových labelů
- profily pro konkrétní PDF/obec

Jednoduše: **co jsme načetli a jak to chceme číst**.

### `up_stg`

Sem patří mezivýsledky algoritmu.

Obsah:
- kandidátní polygony
- rozpad na single polygons
- přiřazení stylů
- přiřazení textů
- residual/missing/extra kandidáti
- confidence / diagnostics

Jednoduše: **pracovní výsledek před lidskou kontrolou**.

### `up_manual`

Sem patří zásahy člověka.

Obsah:
- potvrzení polygonu
- oprava hranice
- změna labelu
- zamítnutí kandidáta
- poznámka reviewera

Jednoduše: **ruční pravda a korekce**.

### `up_core`

Sem patří schválená stabilní data.

Obsah:
- `up_def`
- `up_type_def`
- finální `vector_output`
- finální vazby `up_id` a `up_type_id`

Jednoduše: **výstup, kterému už aplikace smí věřit**.

### `up_api`

Sem patří pouze view / read modely pro frontend, orchestration engine a externí nástroje.

Obsah:
- mapové view
- review view
- export view
- diagnostics view

Jednoduše: **bezpečné čtecí rozhraní**.

## Tvrdé pravidlo

`up_core` nesmí být plněné přímo z PDF extrakce.

Správný tok je:

```text
up_import.vector_import
→ up_import.vector_def / up_import.up_text_def
→ up_stg.vector_stg_*
→ up_manual corrections
→ up_core.vector_output
→ up_api views
```

Pokud algoritmus nemá jistotu, výsledek zůstává v `up_stg` nebo `up_manual`, ne v `up_core`.


## v9 doplnění

### Ruční opravy polygonů

Ruční úpravy hranic nepatří do `up_import` ani přímo do `up_core`.

Patří do:

```text
up_manual.polygon_edit_session
```

Tím zůstane jasné:
- co vytvořil algoritmus
- co opravil člověk
- co bylo schváleno jako finální výstup

### Poznámky a labely k polygonům

Poznámky, warningy a ruční labely patří do:

```text
up_manual.polygon_annotation
```

`text_id` je text vytažený z PDF. Ruční poznámka ho nesmí přepsat.

### Automatické návrhy legendy

Nástroj má sám navrhnout definice stylů z legendy a z pozorovaných PDF stylů.

Pracovní návrhy patří do:

```text
up_stg.vector_def_candidate
up_stg.up_text_def_candidate
```

Schválené definice patří do:

```text
up_import.vector_def
up_import.up_text_def
```

Člověk nebo agent musí vidět důkaz: crop legendy, styl, barvu, čáru, dash, hatch, text label.
