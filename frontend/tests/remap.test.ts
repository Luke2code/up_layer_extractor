import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

import { classTypeValue, inferType, remapProperties, type RemapConfig } from "../src/lib/remap";

const config = JSON.parse(readFileSync(new URL("../public/vector_layer_class_type_remap.json", import.meta.url), "utf-8")) as RemapConfig;

describe("remapping", () => {
  it("maps type evidence to class_type suffixes", () => {
    expect(inferType("stav stabilizovane", config).type).toBe("STAV");
    expect(inferType("návrh změny", config).type).toBe("NAVRH");
    expect(inferType("rezerva", config).type).toBe("REZERVA");
    expect(classTypeValue("BI", "STAV")).toBe("BI.1");
    expect(classTypeValue("Z", "NAVRH")).toBe("Z.2");
    expect(classTypeValue("R", "REZERVA")).toBe("R.3");
  });

  it("keeps known and unknown classes distinct", () => {
    expect(remapProperties({ LAYER: "RZVP", CLASS: "BI", TYPE: "STAV" }, config).requires_manual_review).toBe(false);
    expect(remapProperties({ LAYER: "ZMEN", CLASS: "Z" }, config).proposed_type).toBe("NAVRH");
    const unknown = remapProperties({ LAYER: "RZVP", CLASS: "QQ", TYPE: "STAV" }, config);
    expect(unknown.proposed_class).toBe("UNMAPPED");
    expect(unknown.requires_manual_review).toBe(true);
  });

  it("requires custom REF unless supplied", () => {
    expect(remapProperties({ LAYER: "CUST", CLASS: "X", TYPE: "NAVRH" }, config).requires_manual_review).toBe(true);
    expect(remapProperties({ LAYER: "CUST", CLASS: "X", TYPE: "NAVRH" }, config, "local label").requires_manual_review).toBe(false);
  });
});

