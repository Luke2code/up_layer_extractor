import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

import { DEFAULT_FILTERS, filterOptions, hasMultiPolygon, normalizeFeatureCollection, passesFilter, reconcileFilters } from "../src/lib/geo";
import type { FeatureCollection } from "../src/types";

const sample = normalizeFeatureCollection(
  JSON.parse(readFileSync(new URL("../public/kvetnice_up_layers_unified_pagecoords.geojson", import.meta.url), "utf-8")) as FeatureCollection
);

describe("geo helpers", () => {
  it("preserves Kvetnice field contract and single polygon gate", () => {
    expect(sample.features).toHaveLength(112);
    expect(hasMultiPolygon(sample)).toBe(false);
    for (const feature of sample.features) {
      expect(feature.properties.LAYER_CLASS).toBe(`${feature.properties.LAYER}.${feature.properties.CLASS}`);
      expect(feature.properties.class_type).toMatch(/\.[123]$/);
      expect(feature.geometry.type).toBe("Polygon");
    }
  });

  it("builds dependent filter options", () => {
    const filters = { ...DEFAULT_FILTERS, LAYER: "ZMEN" };
    const options = filterOptions(sample.features, filters);
    expect(options.layers).toContain("RZVP");
    expect(options.layers).toContain("ZMEN");
    expect(options.classes).toContain("Z");
    expect(options.types).toEqual(["ALL", "NAVRH"]);
  });

  it("reconciles invalid dependent filters", () => {
    const next = reconcileFilters(sample.features, { LAYER: "ZMEN", CLASS: "BI", TYPE: "STAV", IS_CLOSED: "ALL" });
    expect(next.CLASS).toBe("ALL");
    expect(next.TYPE).toBe("ALL");
    expect(sample.features.filter((feature) => passesFilter(feature, { ...next, CLASS: "Z" })).every((feature) => feature.properties.CLASS === "Z")).toBe(true);
  });
});

