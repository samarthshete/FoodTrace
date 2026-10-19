// The voice assistant's understanding and answers (spec 023). Pure: keyword rules, checks on
// the LLM's structured output, and templates over a product's label data. No network here.

export type Condition =
  | "diabetes" | "teeth" | "blood_pressure" | "heart" | "weight" | "gluten" | "dairy" | "nuts"
  | "vegan" | "vegetarian";
export type Topic = "score" | "additives" | "sugar" | "salt" | "fat" | "allergens" | "alternatives";

// ASSIST-1: phrases are matched as whole words, longest first.
const CONDITION_WORDS: Record<Condition, string[]> = {
  diabetes: ["diabetes", "diabetic", "blood sugar", "prediabetic", "prediabetes", "insulin"],
  blood_pressure: ["blood pressure", "hypertension", "high blood pressure", "sodium"],
  teeth: ["teeth", "tooth", "dental", "cavities", "cavity", "dentist"],
  heart: ["heart", "cholesterol", "cardiac"],
  weight: ["weight", "calories", "calorie", "diet", "dieting", "lose weight", "losing weight"],
  gluten: ["gluten", "celiac", "coeliac", "gluten free", "gluten intolerant"],
  dairy: ["lactose", "lactose intolerant", "dairy", "milk allergy", "dairy free"],
  nuts: ["nut allergy", "peanut allergy", "nut", "nuts", "peanut", "peanuts", "tree nut"],
  vegan: ["vegan"],
  vegetarian: ["vegetarian"],
};
const TOPIC_WORDS: Record<Topic, string[]> = {
  score: ["score", "rating", "healthy", "how good", "good for me"],
  additives: ["additive", "additives", "e number", "e numbers", "preservative", "preservatives"],
  sugar: ["sugar", "sugars", "sweet"],
  salt: ["salt", "salty"],
  fat: ["fat", "fats", "saturated", "fatty"],
  allergens: ["allergen", "allergens", "allergy", "allergies"],
  alternatives: ["alternative", "alternatives", "instead", "healthier", "better option", "swap"],
};
// ASSIST-2: words that are never part of a product name.
const FILLER = new Set(
  ("hey hi hello ok okay assistant please could would can you tell me more about the a an is it its it's " +
    "i i'm im am have has had my me we our someone somebody person people with who what whats what's " +
    "how much many does do did eat eating drink drinking have having buy should shouldn't fine good bad " +
    "for of in on to this that these those any some product products food item there are be if and or " +
    "but so like just really still also know want check give info information details contain contains " +
    "containing free intolerant intolerance allergic type 1 2 one two kid kids child children son daughter " +
    "safe alright issue issues problem problems condition trouble ok okay which brand brands best recommend " +
    "suggest").split(" "),
);

export type ConcernNutrient = "sugars" | "fat" | "saturated_fat" | "salt" | "fibre" | "energy";
/** ASSIST-14: a health concern outside the fixed conditions, as the LLM understood it. */
export interface Concern {
  label: string;
  nutrients: ConcernNutrient[];
}

export interface Parsed {
  conditions: Condition[];
  topics: Topic[];
  productQuery: string | null;
  concerns?: Concern[];
  /** ASSIST-16: the product words name a broad type ("chocolate"), not one product. */
  generic?: boolean;
}

function normalize(text: string): string {
  return ` ${text.toLowerCase().replace(/['’]/g, "").replace(/[^a-z0-9]+/g, " ").trim()} `;
}

function matchKeys<K extends string>(text: string, table: Record<K, string[]>): { keys: K[]; rest: string } {
  let rest = text;
  const keys: K[] = [];
  const position = new Map<K, number>();
  const entries = (Object.entries(table) as [K, string[]][]).flatMap(([key, words]) =>
    words.map((w) => [key, w] as const),
  );
  entries.sort((a, b) => b[1].length - a[1].length); // longest phrase first
  for (const [key, word] of entries) {
    const needle = ` ${word.replace(/['’]/g, "")} `;
    if (rest.includes(needle)) {
      if (!keys.includes(key)) keys.push(key);
      const at = text.indexOf(needle);
      position.set(key, Math.min(position.get(key) ?? at, at));
      rest = rest.split(needle).join(" ");
    }
  }
  keys.sort((a, b) => (position.get(a) ?? 0) - (position.get(b) ?? 0)); // as the person said them
  return { keys, rest };
}

// "contains milk" is an allergen question; "oat milk" alone is a product name.
const CONTAINS: [RegExp, Condition][] = [
  [/ contains? (milk|dairy|lactose) /, "dairy"],
  [/ contains? (gluten|wheat) /, "gluten"],
  [/ contains? (nuts|nut|peanuts|peanut|tree nuts) /, "nuts"],
];

/** ASSIST-1..3: conditions, topics, and the words naming the product. */
export function parseQuestion(question: string): Parsed {
  let text = normalize(question);
  const extra: Condition[] = [];
  for (const [pattern, condition] of CONTAINS) {
    if (pattern.test(text)) {
      extra.push(condition);
      text = text.replace(pattern, " ");
    }
  }
  const { keys: found, rest: afterConditions } = matchKeys(text, CONDITION_WORDS);
  const conditions = [...extra, ...found.filter((c) => !extra.includes(c))];
  const { keys: topics, rest } = matchKeys(afterConditions, TOPIC_WORDS);
  const words = [...new Set(rest.trim().split(/\s+/).filter((w) => w && !FILLER.has(w)))];
  return { conditions, topics, productQuery: words.length ? words.join(" ") : null };
}

// ---- The LLM's output (ASSIST-13) ------------------------------------------------------------

export const CONDITIONS = Object.keys(CONDITION_WORDS) as Condition[];
export const TOPICS = Object.keys(TOPIC_WORDS) as Topic[];
export const CONCERN_NUTRIENTS: ConcernNutrient[] = ["sugars", "fat", "saturated_fat", "salt", "fibre", "energy"];
const BANNED_LABEL = /safe|tox|danger/i; // hard rule 4, as word stems

function pick<T extends string>(value: unknown, allowed: readonly T[]): T[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.filter((v): v is T => typeof v === "string" && allowed.includes(v as T)))];
}

/** Keeps only what's in the fixed lists; anything else the model says is dropped. */
export function fromModel(raw: unknown): Parsed | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const product = typeof r.product === "string" ? r.product.replace(/\s+/g, " ").trim().slice(0, 80) : "";
  const concerns: Concern[] = [];
  for (const c of Array.isArray(r.other_concerns) ? r.other_concerns : []) {
    if (!c || typeof c !== "object") continue;
    const label = (c as Record<string, unknown>).label;
    if (typeof label !== "string") continue;
    const clean = label.trim().toLowerCase();
    if (!/^[a-z][a-z \-]{0,39}$/.test(clean) || BANNED_LABEL.test(clean)) continue;
    concerns.push({ label: clean, nutrients: pick((c as Record<string, unknown>).nutrients, CONCERN_NUTRIENTS) });
  }
  return {
    conditions: pick(r.conditions, CONDITIONS),
    topics: pick(r.topics, TOPICS),
    productQuery: product || null,
    concerns: concerns.slice(0, 3),
    generic: product !== "" && r.generic_product === true,
  };
}

/** ASSIST-16: ask which product, naming real examples from the search. */
export function clarify(words: string, results: { name: string | null; brand: string | null }[]): string | null {
  const names = [...new Set(results.map((r) => productName({ ...r, gtin: "" } as AssistantProduct)))].slice(0, 3);
  if (names.length < 2) return null;
  const list = names.length === 2 ? names.join(" or ") : `${names[0]}, ${names[1]} or ${names[2]}`;
  return `Which ${words} do you mean? For example: ${list}. Say the brand and name.`;
}

// ---- Answers -------------------------------------------------------------------------------

export interface AssistantProduct {
  gtin: string;
  name: string | null;
  brand: string | null;
  nutrition?: Record<string, { value: number; estimated?: boolean }>;
  allergens?: string[];
  traces?: string[];
  ingredients_text?: string | null;
  ingredients_analysis?: string[];
  allergens_known?: boolean;
  additives?: { name: string }[];
  score: {
    status: "scored" | "not_scored";
    total: number | null;
    band: { label: string } | null;
    nutriscore: { class: string; grade: string | null };
  };
}

type Level = "low" | "medium" | "high";
type Nutrient = "sugars_g" | "fat_g" | "saturated_fat_g" | "salt_g";
// ASSIST-5: UK Food Standards Agency front-of-pack thresholds, per 100 g (foods) / 100 ml (drinks).
// https://www.gov.uk/government/publications/front-of-pack-nutrition-labelling-guidance
export const THRESHOLDS: Record<"food" | "drink", Record<Nutrient, [number, number]>> = {
  food: { sugars_g: [5, 22.5], fat_g: [3, 17.5], saturated_fat_g: [1.5, 5], salt_g: [0.3, 1.5] },
  drink: { sugars_g: [2.5, 11.25], fat_g: [1.5, 8.75], saturated_fat_g: [0.75, 2.5], salt_g: [0.3, 0.75] },
};
const LABELS: Record<Nutrient, string> = {
  sugars_g: "sugars", fat_g: "fat", saturated_fat_g: "saturated fat", salt_g: "salt",
};
export const DISCLAIMER =
  "This is general label information, not medical advice. Your doctor or dietitian can tell you what fits your plan.";

export function level(value: number, nutrient: Nutrient, kind: "food" | "drink"): Level {
  const [low, high] = THRESHOLDS[kind][nutrient];
  return value <= low ? "low" : value > high ? "high" : "medium";
}

function round(value: number): string {
  return String(Number(value.toFixed(value < 10 ? 2 : 1))); // ASSIST-17: 1.52 never reads as 1.5
}

const BRAND_FILLER = new Set(["the", "company", "co", "inc", "llc", "foods", "food", "brands", "corp"]);
const words = (text: string) => text.toLowerCase().replace(/['’]/g, "").split(/[^a-z0-9]+/).filter(Boolean);

function productName(p: AssistantProduct): string {
  const raw = p.name ?? "this product";
  const name = raw === raw.toLowerCase() ? raw.charAt(0).toUpperCase() + raw.slice(1) : raw;
  if (!p.brand) return name;
  // "Reese's Reese's cups", "The Hershey Company Hershey's": the name already says the brand.
  const brandWords = words(p.brand).filter((w) => !BRAND_FILLER.has(w));
  const nameWords = words(name);
  const named = brandWords.some((b) => nameWords.some((n) => n.startsWith(b) || b.startsWith(n) && n.length >= 4));
  return named ? name : `${p.brand} ${name}`;
}

function nutrientSentence(p: AssistantProduct, nutrient: Nutrient): string {
  const kind = p.score.nutriscore.class === "beverage" ? "drink" : "food";
  const per = kind === "drink" ? "per 100 ml" : "per 100 g";
  const value = p.nutrition?.[nutrient]?.value;
  if (value === undefined) return `The label doesn't list its ${LABELS[nutrient]}.`;
  const [low, high] = THRESHOLDS[kind][nutrient];
  const lvl = level(value, nutrient, kind);
  const range = lvl === "high" ? `high is over ${high} g` : lvl === "low" ? `low is ${low} g or less` : `medium is ${low}–${high} g`;
  return `${LABELS[nutrient][0].toUpperCase()}${LABELS[nutrient].slice(1)}: ${round(value)} g ${per}, which is ${lvl} (${range}).`;
}

// ASSIST-17: words in the ingredient text, for when the allergen tags are missing.
const INGREDIENT_WORDS: Record<"nuts" | "peanuts" | "gluten" | "milk", RegExp> = {
  peanuts: /\bpeanuts?\b/i,
  nuts: /\b(almonds?|cashews?|hazelnuts?|walnuts?|pecans?|pistachios?|macadamias?|tree nuts?)\b/i,
  gluten: /\b(wheat|barley|rye|spelt|gluten)\b/i,
  milk: /\b(?<!(coconut|almond|oat|soy|rice|cashew) )milk\b|\b(lactose|whey|casein(ate)?)\b/i,
};

function mentions(p: AssistantProduct, key: keyof typeof INGREDIENT_WORDS): boolean {
  return !!p.ingredients_text && INGREDIENT_WORDS[key].test(p.ingredients_text);
}

const ALLERGEN_TAGS: Partial<Record<Condition, { tag: string; label: string }>> = {
  gluten: { tag: "en:gluten", label: "gluten" },
  dairy: { tag: "en:milk", label: "milk" },
  nuts: { tag: "en:nuts", label: "tree nuts" },
};

function allergenSentences(p: AssistantProduct, condition: Condition): string[] {
  const listed = new Set(p.allergens_known ? (p.allergens ?? []) : []);
  const traces = new Set(p.traces ?? []);
  if (condition === "nuts") {
    const nuts = ["en:nuts", "en:peanuts"].filter((t) => listed.has(t));
    if (nuts.length) return [`The label lists ${nuts.map((t) => (t === "en:nuts" ? "tree nuts" : "peanuts")).join(" and ")}.`];
    const inText = [mentions(p, "peanuts") && "peanuts", mentions(p, "nuts") && "tree nuts"].filter(Boolean);
    if (inText.length) return [`The ingredients mention ${inText.join(" and ")}.`];
    if (!p.allergens_known) return [UNKNOWN_ALLERGENS];
    if (["en:nuts", "en:peanuts"].some((t) => traces.has(t))) return ["The label says it may contain nuts."];
    return ["The label doesn't list nuts or peanuts."];
  }
  const a = ALLERGEN_TAGS[condition]!;
  if (listed.has(a.tag)) return [`The label lists ${a.label}.`];
  if (mentions(p, condition === "dairy" ? "milk" : "gluten")) return [`The ingredients mention ${a.label}.`];
  if (!p.allergens_known) return [UNKNOWN_ALLERGENS];
  if (traces.has(a.tag)) return [`The label says it may contain ${a.label}.`];
  return [`The label doesn't list ${a.label}.`];
}
const UNKNOWN_ALLERGENS = "The allergen information for this product isn't available, so check the label.";

function dietSentence(p: AssistantProduct, diet: "vegan" | "vegetarian"): string {
  const tags = new Set(p.ingredients_analysis ?? []);
  if (tags.has(`en:${diet}`)) return `The ingredient analysis says it's ${diet}.`;
  if (tags.has(`en:non-${diet}`)) return `The ingredient analysis says it isn't ${diet}.`;
  return `It isn't clear from the ingredients whether it's ${diet}.`;
}

const CONDITION_INTRO: Record<Condition, string> = {
  diabetes: "For blood sugar",
  teeth: "For teeth",
  blood_pressure: "For blood pressure",
  heart: "For heart health",
  weight: "For weight",
  gluten: "For gluten",
  dairy: "For dairy",
  nuts: "For nut allergies",
  vegan: "For a vegan diet",
  vegetarian: "For a vegetarian diet",
};

function conditionSentences(p: AssistantProduct, c: Condition): string[] {
  switch (c) {
    case "diabetes": {
      const out = [nutrientSentence(p, "sugars_g")];
      const fibre = p.nutrition?.fiber_g?.value;
      if (fibre !== undefined) out.push(`It has ${round(fibre)} g of fibre per 100 g.`);
      return out;
    }
    case "teeth":
      return [nutrientSentence(p, "sugars_g")];
    case "blood_pressure":
      return [nutrientSentence(p, "salt_g")];
    case "heart":
      return [nutrientSentence(p, "saturated_fat_g"), nutrientSentence(p, "fat_g")];
    case "weight":
      return [energySentence(p), nutrientSentence(p, "sugars_g"), nutrientSentence(p, "fat_g")];
    case "vegan":
    case "vegetarian":
      return [dietSentence(p, c)];
    default:
      return allergenSentences(p, c);
  }
}

function energySentence(p: AssistantProduct): string {
  const kj = p.nutrition?.energy_kj?.value;
  return kj === undefined ? "The label doesn't list its energy." : `It has ${Math.round(kj / 4.184)} kcal per 100 g.`;
}

function fibreSentence(p: AssistantProduct): string {
  const fibre = p.nutrition?.fiber_g?.value;
  return fibre === undefined ? "The label doesn't list its fibre." : `It has ${round(fibre)} g of fibre per 100 g.`;
}

const CONCERN_SENTENCE: Record<ConcernNutrient, (p: AssistantProduct) => string> = {
  sugars: (p) => nutrientSentence(p, "sugars_g"),
  fat: (p) => nutrientSentence(p, "fat_g"),
  saturated_fat: (p) => nutrientSentence(p, "saturated_fat_g"),
  salt: (p) => nutrientSentence(p, "salt_g"),
  fibre: fibreSentence,
  energy: energySentence,
};

/** ASSIST-14 */
function concernSentence(p: AssistantProduct, c: Concern): string {
  if (!c.nutrients.length) return `I don't have specific label guidance for ${c.label}.`;
  return `For ${c.label}: ${c.nutrients.map((n) => CONCERN_SENTENCE[n](p)).join(" ")}`;
}

function scoreSentence(p: AssistantProduct): string {
  const s = p.score;
  if (s.status === "not_scored" || s.total === null) return "It isn't scored: the label data is incomplete.";
  const grade = s.nutriscore.grade ? `, Nutri-Score ${s.nutriscore.grade.toUpperCase()}` : "";
  return `Its overall score is ${s.total} out of 100 (${s.band?.label ?? "unrated"}${grade}).`;
}

function topicSentences(p: AssistantProduct, t: Topic): string[] {
  switch (t) {
    case "sugar":
      return [nutrientSentence(p, "sugars_g")];
    case "salt":
      return [nutrientSentence(p, "salt_g")];
    case "fat":
      return [nutrientSentence(p, "fat_g"), nutrientSentence(p, "saturated_fat_g")];
    case "additives": {
      const adds = p.additives ?? [];
      return [adds.length ? `It has ${adds.length} ${adds.length === 1 ? "additive" : "additives"}: ${adds.map((a) => a.name).join(", ")}.` : "No additives are listed."];
    }
    case "allergens": {
      const names = (p.allergens_known ? (p.allergens ?? []) : []).map((t) => t.replace(/^en:/, "").replace(/-/g, " "));
      if (names.length) return [`The label lists these allergens: ${names.join(", ")}.`];
      const inText = (["peanuts", "nuts", "gluten", "milk"] as const).filter((k) => mentions(p, k));
      if (inText.length) return [`The ingredients mention ${inText.map((k) => (k === "nuts" ? "tree nuts" : k)).join(", ")}.`];
      return [p.allergens_known ? "The label lists no allergens." : UNKNOWN_ALLERGENS];
    }
    case "alternatives":
      return ["Open the product page to see better-scored alternatives in the same category."];
    default:
      return [];
  }
}

/** ASSIST-4..7: the answer for one product. */
export function answerFor(p: AssistantProduct, parsed: Parsed): string {
  const parts = [`${productName(p)}.`];
  for (const c of parsed.conditions) parts.push(`${CONDITION_INTRO[c]}: ${conditionSentences(p, c).join(" ")}`);
  for (const c of parsed.concerns ?? []) parts.push(concernSentence(p, c));
  const said = new Set(parts.join(" ").match(/(Sugars|Salt|Fat|Saturated fat): /g) ?? []);
  const allergy = parsed.conditions.some((c) => c === "nuts" || c === "gluten" || c === "dairy");
  for (const t of parsed.topics.filter((t) => t !== "score" && !(t === "allergens" && allergy))) {
    // Don't repeat a nutrient a condition or concern already covered.
    parts.push(...topicSentences(p, t).filter((x) => !said.has(x.slice(0, x.indexOf(": ") + 2))));
  }
  parts.push(scoreSentence(p));
  parts.push(DISCLAIMER);
  return parts.join(" ");
}

export const NEED_PRODUCT = "Which product? Say its brand and name, like \"Pringles Original\".";
export const NOT_AVAILABLE = "I can't look that up right now. Please try again in a moment.";
export const notFound = (words: string) =>
  `I couldn't find "${words}". Try the brand and product name, or scan its barcode.`;
