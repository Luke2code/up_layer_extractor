# up_layer_extractor instruction pack v9

Status: reviewed / revalidated from scratch.

This update keeps the v8 schema model and adds the missing operator/review capabilities:

- manual border adjustment of a selected polygon
- polygon labels and notes
- auto-generated legend/style definition candidates
- explicit selection/approval of legend definitions
- stronger provenance from raw PDF drawing → staging candidate → manual correction → core output
- blind-spot fixes and validation gates

Canonical data flow stays:

```text
up_import → up_stg → up_manual → up_core → up_api
```

Do not change the extraction business logic casually. New PDFs must first go through diagnostics and algorithm routing.


## v10 custom remapping
This pack includes uploaded legacy-style mapping config for layer/class/type normalization. See `CUSTOM_LAYER_CLASS_TYPE_REMAPPING.md` and `config/vector_layer_class_type_remap.json`.

## Reference prototype

This pack includes working prototype reference files under `reference_prototype/`. See `REFERENCE_PROTOTYPE_MANIFEST.md`.
