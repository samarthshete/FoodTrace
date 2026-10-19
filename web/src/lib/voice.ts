// Answers to spoken or typed questions about a product (spec 022). Pure: fixed rules over the
// page's own data. No AI model, no network.
import type { Alternatives, Breakdown, Product } from "./api";
import { type Allergen, ALLERGENS } from "./allergens";

export type Intent = "allergen" | "alternatives" | "why" | "additives" | "score" | "summary" | "help";

// VOICE-1: checked in this order; the first intent with a matching keyword wins.
const KEYWORDS: [Exclude<Intent, "help">, string[]][] = [
  ["allergen", ["contain", "allergen", "gluten", "milk", "dairy", "nut", "peanut", "soy", "egg",
    "sesame", "fish", "shellfish", "wheat"]],
  ["alternatives", ["alternative", "instead", "healthier", "better", "swap"]],
  ["why", ["why", "lower", "reason", "bad", "good"]],
  ["additives", ["additive", "e number", "preservative", "color", "colour"]],
  ["score", ["score", "healthy", "rating", "how good"]],
  ["summary", ["read", "tell me", "about", "summary"]],
];

// The words people use for each major allergen.
const ALIASES: Record<Allergen, string[]> = {
  milk: ["milk", "dairy", "lactose"],
  eggs: ["egg", "eggs"],
  fish: ["fish"],
  crustacean_shellfish: ["shellfish", "shrimp", "crab", "lobster", "crustacean", "crustaceans"],
  tree_nuts: ["nut", "nuts", "tree nut", "tree nuts", "almond", "almonds", "cashew", "cashews"],
  peanuts: ["peanut", "peanuts"],
  wheat: ["wheat", "gluten"],
  soybeans: ["soy", "soya", "soybean", "soybeans"],
  sesame: ["sesame"],
};

export const HELP =
  "You can ask about the score, why it got that score, its additives, allergens, or healthier alternatives.";

function words(text: string): string {
  return ` ${text.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()} `;
}

export function intentOf(question: string): Intent {
  const q = words(question);
  for (const [intent, keys] of KEYWORDS) {
    if (keys.some((k) => q.includes(` ${k} `) || q.includes(` ${k}s `))) return intent;
  }
  return "help";
}

export interface PageData {
  product: Product;
  breakdown: Breakdown;
  alternatives?: Alternatives | null;
}

function scoreSentence({ product }: PageData): string {
  const s = product.score;
  if (s.status === "not_scored") {
    return `${product.name ?? "This product"} isn't scored: the label data is incomplete.`;
  }
  return `${product.name ?? "This product"} scores ${s.total} out of 100, which is ${s.band?.label ?? "unrated"}.`;
}

function allergenAnswer(question: string, { product }: PageData): string {
  if (!product.allergens_known) {
    return "Allergen information isn't available for this product. Check the label."; // VOICE-3
  }
  const q = words(question);
  const listed = new Set(product.allergens ?? []);
  const asked = (Object.keys(ALIASES) as Allergen[])
    .filter((key) => ALIASES[key].some((alias) => q.includes(` ${alias} `)))
    .map((key) => ALLERGENS[key]);
  if (asked.length) {
    return asked
      .map(({ label, tag }) =>
        listed.has(tag) ? `The label lists ${label.toLowerCase()}.` : `The label doesn't list ${label.toLowerCase()}.`,
      )
      .join(" ");
  }
  const named = Object.values(ALLERGENS).filter(({ tag }) => listed.has(tag)).map(({ label }) => label.toLowerCase());
  return named.length ? `The label lists ${named.join(", ")}.` : "The label doesn't list any of the major allergens.";
}

function additivesAnswer({ breakdown }: PageData): string {
  const lines = breakdown.score.breakdown.filter((l) => l.component === "additives" && l.rule_id !== "additives.cap" && !l.rule_id.startsWith("component."));
  if (!lines.length) return "No additives were found in the ingredient list.";
  const names = lines.map((l) => (l.input_value as { name?: string } | null)?.name ?? l.rule_id.replace("additives.", "").toUpperCase());
  return `It has ${names.length} ${names.length === 1 ? "additive" : "additives"}: ${names.join(", ")}.`;
}

function alternativesAnswer({ alternatives }: PageData): string {
  const items = alternatives?.alternatives ?? [];
  if (!items.length) return "I don't have better-scored alternatives for this product yet.";
  const top = items.slice(0, 3).map((a) => `${a.name ?? "an unnamed product"}, ${a.total} out of 100`);
  return `Better-scored options in the same category: ${top.join("; ")}.`;
}

/** VOICE-2: one answer from the page's data. */
export function answer(question: string, data: PageData): string {
  const explanation = data.breakdown.explanation;
  switch (intentOf(question)) {
    case "score":
      return scoreSentence(data);
    case "why":
      return explanation.slice(1).join(" ") || scoreSentence(data);
    case "additives":
      return additivesAnswer(data);
    case "allergen":
      return allergenAnswer(question, data);
    case "alternatives":
      return alternativesAnswer(data);
    case "summary":
      return summary(data);
    default:
      return HELP; // VOICE-4
  }
}

/** VOICE-5: what "Read aloud" says. */
export function summary(data: PageData): string {
  return [scoreSentence(data), ...data.breakdown.explanation.slice(1)].join(" ");
}
