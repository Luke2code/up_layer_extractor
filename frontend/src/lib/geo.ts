import type { FeatureCollection, FeatureProperties, Filters, GeoFeature, Ring } from "../types";

export const PAGE = { width: 1191.005, height: 1683.751 };

export const DEFAULT_FILTERS: Filters = {
  LAYER: "ALL",
  CLASS: "ALL",
  TYPE: "ALL",
  IS_CLOSED: "ALL"
};

export const CLASS_COLORS: Record<string, string> = {
  BI: "#d9483f",
  BV: "#ce6f58",
  BH: "#c75c91",
  BU: "#d85b52",
  "BX.c": "#b95672",
  "BX.p": "#b66b8a",
  "BX.r": "#a26192",
  SV: "#d98989",
  SC: "#cc7f9f",
  SX: "#bb8fce",
  SK: "#bb8fce",
  Z: "#d5c36b",
  RI: "#86b37f",
  RX: "#74a36d",
  RN: "#86b37f",
  P: "#b3b3b3",
  T: "#9aa7c7",
  UNMAPPED: "#9ca3af"
};

export function classType(className?: string, typeName?: string): string | undefined {
  if (!className || !typeName) return undefined;
  const suffix = typeName === "STAV" ? "1" : typeName === "NAVRH" ? "2" : typeName === "REZERVA" ? "3" : "0";
  return `${className}.${suffix}`;
}

export function ensureProps(feature: GeoFeature): FeatureProperties {
  const props = feature.properties ?? {};
  if (!props.LAYER_CLASS && props.LAYER && props.CLASS) {
    props.LAYER_CLASS = `${props.LAYER}.${props.CLASS}`;
  }
  if (!props.class_type && props.CLASS && props.TYPE) {
    props.class_type = classType(props.CLASS, props.TYPE);
  }
  if (props.IS_CLOSED === undefined) {
    const firstRing = rings(feature)[0];
    props.IS_CLOSED = Boolean(firstRing && ringIsClosed(firstRing));
  }
  feature.properties = props;
  return props;
}

export function normalizeFeatureCollection(collection: FeatureCollection): FeatureCollection {
  collection.features.forEach(ensureProps);
  collection.feature_count = collection.feature_count ?? collection.features.length;
  collection.source_type = collection.source_type ?? "local_geojson";
  collection.classification_status = collection.classification_status ?? "requires_review";
  return collection;
}

export function rings(feature: GeoFeature): Ring[] {
  if (feature.geometry.type !== "Polygon") return [];
  return feature.geometry.coordinates as Ring[];
}

export function ringIsClosed(ring: Ring): boolean {
  if (ring.length < 4) return false;
  const first = ring[0];
  const last = ring[ring.length - 1];
  return Math.abs(first[0] - last[0]) < 1e-6 && Math.abs(first[1] - last[1]) < 1e-6;
}

export function closeRing(ring: Ring): Ring {
  if (ringIsClosed(ring) || ring.length === 0) return ring;
  const first = ring[0];
  return [...ring, [first[0], first[1]]];
}

export function ringArea(ring: Ring): number {
  const closed = closeRing(ring);
  let total = 0;
  for (let index = 0; index < closed.length - 1; index += 1) {
    const left = closed[index];
    const right = closed[index + 1];
    total += left[0] * right[1] - right[0] * left[1];
  }
  return total / 2;
}

export function polygonArea(feature: GeoFeature): number {
  const featureRings = rings(feature);
  if (!featureRings.length) return 0;
  const outer = Math.abs(ringArea(featureRings[0]));
  const holes = featureRings.slice(1).reduce((sum, ring) => sum + Math.abs(ringArea(ring)), 0);
  return Math.max(0, outer - holes);
}

export function pathForRing(ring: Ring): string {
  return ring.map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x} ${y}`).join(" ") + " Z";
}

export function pathForRings(featureRings: Ring[]): string {
  return featureRings.map(pathForRing).join(" ");
}

export function centerOfRing(ring: Ring): { x: number; y: number } {
  if (!ring.length) return { x: 0, y: 0 };
  const [sumX, sumY] = ring.reduce(([x, y], point) => [x + point[0], y + point[1]], [0, 0]);
  return { x: sumX / ring.length, y: sumY / ring.length };
}

export function uniq(values: Array<string | number | boolean | null | undefined>): string[] {
  return [...new Set(values.filter((value) => value !== undefined && value !== null).map(String))].sort();
}

export function filterOptions(features: GeoFeature[], filters: Filters) {
  const layers = ["ALL", ...uniq(features.map((feature) => feature.properties.LAYER))];
  const layerFiltered = filters.LAYER === "ALL" ? features : features.filter((feature) => feature.properties.LAYER === filters.LAYER);
  const classes = ["ALL", ...uniq(layerFiltered.map((feature) => feature.properties.CLASS))];
  const classFiltered = filters.CLASS === "ALL" ? layerFiltered : layerFiltered.filter((feature) => feature.properties.CLASS === filters.CLASS);
  const types = ["ALL", ...uniq(classFiltered.map((feature) => feature.properties.TYPE))];
  return { layers, classes, types, closed: ["ALL", "TRUE", "FALSE"] };
}

export function reconcileFilters(features: GeoFeature[], filters: Filters): Filters {
  const options = filterOptions(features, filters);
  const next = { ...filters };
  if (!options.layers.includes(next.LAYER)) {
    next.LAYER = "ALL";
    next.CLASS = "ALL";
    next.TYPE = "ALL";
  }
  if (!options.classes.includes(next.CLASS)) {
    next.CLASS = "ALL";
    next.TYPE = "ALL";
  }
  if (!options.types.includes(next.TYPE)) {
    next.TYPE = "ALL";
  }
  return next;
}

export function passesFilter(feature: GeoFeature, filters: Filters): boolean {
  const props = feature.properties;
  return (
    (filters.LAYER === "ALL" || props.LAYER === filters.LAYER) &&
    (filters.CLASS === "ALL" || props.CLASS === filters.CLASS) &&
    (filters.TYPE === "ALL" || props.TYPE === filters.TYPE) &&
    (filters.IS_CLOSED === "ALL" || String(props.IS_CLOSED).toUpperCase() === filters.IS_CLOSED)
  );
}

export function hasMultiPolygon(collection: FeatureCollection): boolean {
  return collection.features.some((feature) => feature.geometry.type === "MultiPolygon");
}

export function cloneFeature(feature: GeoFeature): GeoFeature {
  return JSON.parse(JSON.stringify(feature)) as GeoFeature;
}

export function updateOuterRing(feature: GeoFeature, ring: Ring): GeoFeature {
  const next = cloneFeature(feature);
  const currentRings = rings(next);
  next.geometry.coordinates = [closeRing(ring), ...currentRings.slice(1)];
  ensureProps(next);
  return next;
}

export function featureCountByLayerClass(features: GeoFeature[]): Array<{ key: string; count: number }> {
  const counts = new Map<string, number>();
  for (const feature of features) {
    const props = feature.properties;
    const key = `${props.LAYER_CLASS ?? "UNMAPPED"} / ${props.TYPE ?? "UNMAPPED"}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([key, count]) => ({ key, count }));
}
