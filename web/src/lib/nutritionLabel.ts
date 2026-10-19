// Parse a US Nutrition Facts panel from OCR text (spec 017, CONTRIB-2). Pure: no I/O.
// Values on the label are per serving; they're converted to per 100 g using the serving
// size. A value that can't be read stays undefined — nothing is guessed.

export interface PerServing {
  calories?: number;
  fat_g?: number;
  saturated_fat_g?: number;
  sodium_mg?: number;
  carbohydrate_g?: number;
  fiber_g?: number;
  sugars_g?: number;
  proteins_g?: number;
}

export interface Per100g {
  energy_kj?: number;
  fat_g?: number;
  saturated_fat_g?: number;
  salt_g?: number;
  fiber_g?: number;
  sugars_g?: number;
  proteins_g?: number;
}

export interface ParsedLabel {
  servingG?: number;
  perServing: PerServing;
  per100g: Per100g;
}

const NUM = String.raw`(\d+(?:[.,]\d+)?)`;
const PATTERNS: Record<keyof PerServing, RegExp> = {
  calories: new RegExp(String.raw`calories\D{0,12}?${NUM}`),
  fat_g: new RegExp(String.raw`total\s*fat\s*${NUM}\s*g`),
  saturated_fat_g: new RegExp(String.raw`sat(?:urated|\.)?\s*fat\s*${NUM}\s*g`),
  sodium_mg: new RegExp(String.raw`sodium\s*${NUM}\s*mg`),
  carbohydrate_g: new RegExp(String.raw`total\s*carb(?:ohydrate|s|\.)?\s*${NUM}\s*g`),
  fiber_g: new RegExp(String.raw`(?:dietary\s*)?fib(?:er|re)\s*${NUM}\s*g`),
  sugars_g: new RegExp(String.raw`(?<!added\s)(?:total\s*)?sugars\s*${NUM}\s*g`),
  proteins_g: new RegExp(String.raw`protein\s*${NUM}\s*g`),
};
const SERVING = new RegExp(String.raw`serving\s*size[^\n]*?\(?\s*${NUM}\s*(g|ml)\b`);

const round = (n: number, digits: number) => Number(n.toFixed(digits));

/** Common OCR slips on labels: "Og" for "0g", "O mg", stray spaces in decimals. */
export function cleanOcr(text: string): string {
  return text
    .toLowerCase()
    .replace(/\bo(?=\s*m?g\b)/g, "0")
    .replace(/(\d)\s*\.\s*(\d)/g, "$1.$2");
}

export function parseLabel(text: string): ParsedLabel {
  const clean = cleanOcr(text);
  const perServing: PerServing = {};
  for (const [field, pattern] of Object.entries(PATTERNS) as [keyof PerServing, RegExp][]) {
    const m = clean.match(pattern);
    if (m) perServing[field] = Number(m[1].replace(",", "."));
  }
  const serving = clean.match(SERVING);
  const servingG = serving ? Number(serving[1].replace(",", ".")) : undefined;
  return { servingG, perServing, per100g: toPer100g(perServing, servingG) };
}

export function toPer100g(s: PerServing, servingG: number | undefined): Per100g {
  if (!servingG || servingG <= 0) return {};
  const f = 100 / servingG;
  const g = (v: number | undefined) => (v === undefined ? undefined : round(v * f, 2));
  return {
    energy_kj: s.calories === undefined ? undefined : round(s.calories * 4.184 * f, 0),
    fat_g: g(s.fat_g),
    saturated_fat_g: g(s.saturated_fat_g),
    salt_g: s.sodium_mg === undefined ? undefined : round((s.sodium_mg / 1000) * 2.5 * f, 3),
    fiber_g: g(s.fiber_g),
    sugars_g: g(s.sugars_g),
    proteins_g: g(s.proteins_g),
  };
}
