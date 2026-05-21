import type { FeatureProperties, RemapResult } from "../types";

export interface RemapConfig {
  version: string;
  source: string;
  CLASS_TYPE_CONFIG: Record<string, string[]>;
  CLASS_GROUP_MAP: Record<string, string>;
  CLASS_MAP: Record<string, string>;
}

const TYPE_BY_CODE: Record<string, string> = { "1": "STAV", "2": "NAVRH", "3": "REZERVA" };
const CODE_BY_TYPE: Record<string, string> = { STAV: "1", NAVRH: "2", REZERVA: "3" };

function fold(value: string): string {
  return value.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLocaleLowerCase();
}

function evidenceMatches(pattern: string, evidence: string): boolean {
  const regex = new RegExp(fold(pattern).replace(/\?/g, ".*"));
  return regex.test(fold(evidence));
}

export function inferType(rawTypeText: string | undefined | null, config: RemapConfig, layer?: string): { type: string; rule: string; review: boolean; score: number } {
  if (layer === "ZMEN" && !rawTypeText) {
    return { type: "NAVRH", rule: "ZMEN default TYPE=NAVRH", review: false, score: 0.9 };
  }
  if (!rawTypeText) {
    return { type: "UNMAPPED", rule: "missing type evidence", review: true, score: 0 };
  }
  const upper = rawTypeText.toUpperCase();
  if (CODE_BY_TYPE[upper]) {
    return { type: upper, rule: `exact TYPE=${upper}`, review: false, score: 1 };
  }
  const matches = Object.entries(config.CLASS_TYPE_CONFIG).filter(([, patterns]) => patterns.some((pattern) => evidenceMatches(pattern, rawTypeText)));
  if (matches.length === 1) {
    const [code] = matches[0];
    return { type: TYPE_BY_CODE[code], rule: `CLASS_TYPE_CONFIG[${code}]`, review: false, score: 0.82 };
  }
  if (matches.length > 1) {
    return { type: "UNMAPPED", rule: "ambiguous type evidence", review: true, score: 0.2 };
  }
  return { type: "UNMAPPED", rule: "no type evidence matched", review: true, score: 0.1 };
}

export function classTypeValue(className: string, typeName: string): string {
  return `${className}.${CODE_BY_TYPE[typeName] ?? "0"}`;
}

function longestPrefix(value: string, lookup: Record<string, string>): string | null {
  return Object.keys(lookup)
    .filter((key) => value.startsWith(key))
    .sort((a, b) => b.length - a.length)[0] ?? null;
}

export function remapProperties(props: FeatureProperties, config: RemapConfig, ref?: string): RemapResult {
  const rawLayer = props.LAYER ?? "UNCLASSIFIED";
  const rawClass = props.CLASS ?? "UNMAPPED";
  const rawType = (props.TYPE ?? props.legend_symbol ?? undefined) as string | undefined;
  const layerClass = `${rawLayer}.${rawClass}`;
  const inferred = inferType(rawType, config, rawLayer);
  const exactLabel = config.CLASS_MAP[layerClass];
  const groupKey = longestPrefix(layerClass, config.CLASS_GROUP_MAP);
  const groupLabel = groupKey ? config.CLASS_GROUP_MAP[groupKey] : null;

  if (exactLabel) {
    const customMissingRef = layerClass.startsWith("CUST.") && !ref;
    return {
      raw_layer: rawLayer,
      raw_class: rawClass,
      raw_type_text: rawType,
      proposed_layer: rawLayer,
      proposed_class: rawClass,
      proposed_type: inferred.type,
      proposed_layer_class: layerClass,
      proposed_class_type: classTypeValue(rawClass, inferred.type),
      group_label: groupLabel,
      display_label: ref ? `${exactLabel} (${ref})` : exactLabel,
      matched_rule: `CLASS_MAP exact; ${inferred.rule}`,
      match_score: Math.min(0.96, 0.75 + inferred.score / 4),
      requires_manual_review: inferred.review || customMissingRef,
      reason: inferred.review || customMissingRef ? "mapping requires operator review" : "exact class map match"
    };
  }

  if (layerClass.startsWith("CUST.") && ref) {
    return {
      raw_layer: rawLayer,
      raw_class: rawClass,
      raw_type_text: rawType,
      proposed_layer: rawLayer,
      proposed_class: rawClass,
      proposed_type: inferred.type,
      proposed_layer_class: layerClass,
      proposed_class_type: classTypeValue(rawClass, inferred.type),
      group_label: groupLabel,
      display_label: `${layerClass} - ${ref}`,
      matched_rule: `CUST REF; ${inferred.rule}`,
      match_score: 0.78,
      requires_manual_review: inferred.review,
      reason: "custom class accepted with REF evidence"
    };
  }

  return {
    raw_layer: rawLayer,
    raw_class: rawClass,
    raw_type_text: rawType,
    proposed_layer: rawLayer,
    proposed_class: "UNMAPPED",
    proposed_type: inferred.type,
    proposed_layer_class: `${rawLayer}.UNMAPPED`,
    proposed_class_type: classTypeValue("UNMAPPED", inferred.type),
    group_label: groupLabel,
    display_label: null,
    matched_rule: `UNMAPPED; ${inferred.rule}`,
    match_score: inferred.score / 2,
    requires_manual_review: true,
    reason: "class is not in active CLASS_MAP and no explicit custom override exists"
  };
}

export function generateRemapRows(features: FeatureProperties[], config: RemapConfig): RemapResult[] {
  const seen = new Set<string>();
  const rows: RemapResult[] = [];
  for (const props of features) {
    const key = `${props.LAYER}.${props.CLASS}.${props.TYPE}`;
    if (seen.has(key)) continue;
    seen.add(key);
    rows.push(remapProperties(props, config));
  }
  return rows;
}

