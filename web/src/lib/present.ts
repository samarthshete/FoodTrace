// Pure presentation helpers: turn API data into words and numbers for the product page.
// No scoring happens here; everything reads from the API's breakdown (spec 008).

import type { BreakdownLine, Component, ProductAdditive, Score } from "./api";

export const COMPONENT_LABELS: Record<Component, string> = {
  nutrition: "Nutrition",
  additives: "Additives",
  processing: "Processing",
};

const CLASS_LABELS: Record<string, string> = {
  general: "a general food",
  cheese: "a cheese",
  beverage: "a drink",
  fats_oils_nuts_seeds: "a fat, oil, nut or seed",
  water: "water",
};

const NUTRIENTS: Record<string, { label: string; unit: string }> = {
  energy: { label: "Energy", unit: "kJ" },
  energy_from_saturates: { label: "Energy from saturated fat", unit: "kJ" },
  sugars: { label: "Sugars", unit: "g" },
  saturated_fat: { label: "Saturated fat", unit: "g" },
  saturates_ratio: { label: "Share of fat that is saturated", unit: "%" },
  salt: { label: "Salt", unit: "g" },
  sweeteners: { label: "Non-nutritive sweeteners", unit: "" },
  proteins: { label: "Protein", unit: "g" },
  fiber: { label: "Fibre", unit: "g" },
  fvl: { label: "Fruit, vegetables and legumes", unit: "%" },
};

const FIELD_LABELS: Record<string, string> = {
  energy_kj: "energy",
  sugars_g: "sugars",
  saturated_fat_g: "saturated fat",
  fat_g: "fat",
  salt_g: "salt",
  fiber_g: "fibre",
  proteins_g: "protein",
  fvl_percent: "fruit/vegetable share",
  nova_group: "processing level",
  additives: "ingredient list",
};

const RISK_WORDS: Record<number, string> = {
  0: "No estimated overexposure risk (EFSA)",
  1: "Low estimated overexposure risk (EFSA)",
  2: "Moderate estimated overexposure risk (EFSA)",
  3: "High estimated overexposure risk (EFSA)",
};

export const BAND_STYLES: Record<string, string> = {
  excellent: "bg-emerald-100 text-emerald-900 ring-emerald-600",
  good: "bg-lime-100 text-lime-900 ring-lime-600",
  mediocre: "bg-amber-100 text-amber-900 ring-amber-600",
  poor: "bg-rose-100 text-rose-900 ring-rose-600",
};

export function bandStyle(bandId: string | undefined): string {
  return (bandId && BAND_STYLES[bandId]) || "bg-zinc-100 text-zinc-900 ring-zinc-500";
}

export function classLabel(nutriClass: string): string {
  return CLASS_LABELS[nutriClass] ?? nutriClass;
}

export function missingWords(fields: string[]): string[] {
  return fields.map((f) => FIELD_LABELS[f] ?? f);
}

export type DataBadge = { label: string; level: "complete" | "partial" | "limited" };

export function dataBadge(confidence: number): DataBadge {
  if (confidence >= 0.9) return { label: "Complete data", level: "complete" };
  if (confidence >= 0.6) return { label: "Partial data", level: "partial" };
  return { label: "Limited data", level: "limited" };
}

export interface ComponentBar {
  component: Component;
  label: string;
  known: boolean;
  points: number | null; // value × weight, 1 decimal
  weight: number;
  fraction: number; // 0..1 for the bar width
}

export function componentBars(score: Score): ComponentBar[] {
  return (Object.keys(COMPONENT_LABELS) as Component[]).map((component) => {
    const c = score.components[component];
    const value = c.known && c.value !== null ? c.value : null;
    return {
      component,
      label: COMPONENT_LABELS[component],
      known: value !== null,
      points: value === null ? null : Math.round(value * c.weight * 10) / 10,
      weight: c.weight,
      fraction: value ?? 0,
    };
  });
}

export function isRescaled(score: Score): boolean {
  return Object.values(score.components).some((c) => !c.known);
}

/** Rounded for reading (PAGE-15, ENGINE-13): kJ whole; g and % to 1 decimal, or 2 below 1. */
export function displayNumber(value: number, unit: string): string {
  const digits = unit === "kJ" ? 0 : Math.abs(value) < 1 ? 2 : 1;
  return String(Number(value.toFixed(digits)));
}

function formatNumber(value: unknown, unit = ""): string {
  if (typeof value === "number") {
    return unit ? displayNumber(value, unit) : String(Math.round(value * 100) / 100);
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value ?? "");
}

// FDA-6: US regulatory status in words, from FDA's Substances Added to Food inventory.
const US_STATUS: Record<string, string> = {
  food_additive: "US: approved food additive",
  color_additive: "US: approved color additive",
  gras: "US: generally recognized as safe, GRAS",
  prior_sanctioned: "US: prior-sanctioned",
  gras_flavor: "US: flavoring, GRAS per FEMA",
  delisted: "US: color listing ended (delisted)",
  prohibited: "US: prohibited in food",
};

export interface UsStatusView {
  text: string;
  cfr: string | null;
  cfrUrl: string | null;
}

export function usStatusView(additive: ProductAdditive | undefined): UsStatusView | undefined {
  const text = additive?.us_status ? US_STATUS[additive.us_status] : undefined;
  if (!text) return undefined;
  const cfr = additive?.fda_cfr_ref ?? null;
  return {
    text,
    cfr: cfr && `21 CFR ${cfr}`,
    cfrUrl: cfr && `https://www.ecfr.gov/current/title-21/section-${cfr}`,
  };
}

export interface LineView {
  key: string;
  label: string;
  value: string;
  points: string;
  pointsHint: string;
  sourceUrl: string;
  estimated: boolean;
  note?: string;
  usStatus?: UsStatusView;
}

/** One readable row per breakdown line (PAGE-5, PAGE-6). Summary lines are excluded. */
export function lineView(
  line: BreakdownLine,
  weights: Record<Component, number>,
  additives: Map<string, ProductAdditive> = new Map(),
): LineView {
  const base = {
    key: line.rule_id,
    sourceUrl: line.source_url,
    estimated: line.estimated,
    note: line.note,
  };
  if (line.rule_id.startsWith("nutriscore.")) {
    const key = line.rule_id.split(".").at(-1) ?? "";
    const n = NUTRIENTS[key];
    const unit = n?.unit ?? "";
    const value = formatNumber(line.input_value, unit);
    const signed = line.points > 0 ? `+${line.points}` : String(line.points);
    return {
      ...base,
      label: n?.label ?? key,
      value: unit === "%" ? `${value}%` : `${value} ${unit}`.trim(),
      points: line.rule_id === "nutriscore.water" ? "Grade A" : signed,
      pointsHint:
        line.points > 0
          ? "Nutri-Score points against"
          : line.points < 0
            ? "Nutri-Score points in favour"
            : "No Nutri-Score points",
    };
  }
  if (line.rule_id === "additives.cap") {
    return {
      ...base,
      label: "Additive cap",
      value: `Score capped at ${formatNumber(line.input_value)}`,
      points: formatNumber(line.points),
      pointsHint: "Score points",
    };
  }
  if (line.component === "additives") {
    const info = (line.input_value ?? {}) as { name?: string; risk_level?: number | null };
    const risk = info.risk_level;
    const penalty = Math.round(line.points * weights.additives * 10) / 10;
    return {
      ...base,
      note: undefined, // the rating words below already say what the note says
      label: info.name ?? line.rule_id.replace("additives.", "").toUpperCase(),
      usStatus: usStatusView(additives.get(line.rule_id.replace("additives.", ""))),
      value: risk === null || risk === undefined ? "Not rated by EFSA" : RISK_WORDS[risk],
      points: penalty === 0 ? "0" : String(penalty),
      pointsHint: "Score points",
    };
  }
  if (line.rule_id === "processing.nova") {
    return {
      ...base,
      label: "Processing (NOVA)",
      value: line.note ?? `NOVA ${formatNumber(line.input_value)}`,
      note: undefined, // shown as the value
      points: `${Math.round(line.points * weights.processing * 10) / 10}`,
      pointsHint: `Score points out of ${weights.processing}`,
    };
  }
  return {
    ...base,
    label: line.rule_id,
    value: formatNumber(line.input_value),
    points: formatNumber(line.points),
    pointsHint: "Points",
  };
}

/** Why a component has no lines (PAGE-16). */
export function emptyComponentText(score: Score, component: Component): string {
  return component === "additives" && score.components.additives.known
    ? "No additives found in the ingredient list."
    : "No data.";
}

export function groupBreakdown(
  score: Score & { breakdown: BreakdownLine[] },
  additives: ProductAdditive[] = [],
) {
  const byCode = new Map(additives.map((a) => [a.code, a]));
  const weights = {
    nutrition: score.components.nutrition.weight,
    additives: score.components.additives.weight,
    processing: score.components.processing.weight,
  };
  return (Object.keys(COMPONENT_LABELS) as Component[]).map((component) => ({
    component,
    label: COMPONENT_LABELS[component],
    emptyText: emptyComponentText(score, component),
    lines: score.breakdown
      .filter((l) => l.component === component && !l.rule_id.startsWith("component."))
      .map((l) => lineView(l, weights, byCode)),
  }));
}

/** "en:breakfast-cereals" → "In breakfast cereals" (ALT-12). */
export function categoryWords(tag: string): string {
  const words = tag.replace(/^[a-z]{2}:/, "").replace(/-/g, " ").trim().toLowerCase();
  return `In ${words}`;
}

/** "2026-08-01" or an ISO timestamp → "Aug 1, 2026". */
export function formatDate(iso: string): string {
  return new Date(`${iso.slice(0, 10)}T00:00:00Z`).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
