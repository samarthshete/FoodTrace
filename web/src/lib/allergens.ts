// Allergen and diet notes for the signed-in user (spec 018, ACC-7, ACC-8). Pure: no I/O.
// Only label data is used. A product is never called "safe".

export type Allergen =
  | "milk" | "eggs" | "fish" | "crustacean_shellfish" | "tree_nuts" | "peanuts" | "wheat"
  | "soybeans" | "sesame";
export type Diet = "vegan" | "vegetarian" | "gluten_free";

export interface Preferences {
  allergens: Allergen[];
  diets: Diet[];
  save_history: boolean;
}

// The US major nine, with the Open Food Facts tag each one maps to.
export const ALLERGENS: Record<Allergen, { label: string; tag: string }> = {
  milk: { label: "Milk", tag: "en:milk" },
  eggs: { label: "Eggs", tag: "en:eggs" },
  fish: { label: "Fish", tag: "en:fish" },
  crustacean_shellfish: { label: "Crustacean shellfish", tag: "en:crustaceans" },
  tree_nuts: { label: "Tree nuts", tag: "en:nuts" },
  peanuts: { label: "Peanuts", tag: "en:peanuts" },
  wheat: { label: "Wheat", tag: "en:gluten" },
  soybeans: { label: "Soybeans", tag: "en:soybeans" },
  sesame: { label: "Sesame", tag: "en:sesame-seeds" },
};

export const DIETS: Record<Diet, string> = {
  vegan: "Vegan",
  vegetarian: "Vegetarian",
  gluten_free: "Gluten-free",
};

export interface LabelData {
  allergens?: string[];
  traces?: string[];
  ingredients_analysis?: string[];
  allergens_known?: boolean;
}

export interface Notes {
  unknown: boolean;
  contains: string[];
  mayContain: string[];
  diets: string[];
}

export function personalNotes(product: LabelData, prefs: Preferences): Notes {
  const notes: Notes = { unknown: false, contains: [], mayContain: [], diets: [] };
  if (!prefs.allergens.length && !prefs.diets.length) return notes;
  if (!product.allergens_known) return { ...notes, unknown: true };
  const allergens = new Set(product.allergens ?? []);
  const traces = new Set(product.traces ?? []);
  const analysis = new Set(product.ingredients_analysis ?? []);
  for (const key of prefs.allergens) {
    const { label, tag } = ALLERGENS[key];
    if (allergens.has(tag)) notes.contains.push(label);
    else if (traces.has(tag)) notes.mayContain.push(label);
  }
  for (const diet of prefs.diets) {
    if (diet === "vegan" && analysis.has("en:non-vegan")) notes.diets.push("Not vegan");
    if (diet === "vegan" && analysis.has("en:vegan-status-unknown")) notes.diets.push("Vegan status unknown");
    if (diet === "vegetarian" && analysis.has("en:non-vegetarian")) notes.diets.push("Not vegetarian");
    if (diet === "vegetarian" && analysis.has("en:vegetarian-status-unknown"))
      notes.diets.push("Vegetarian status unknown");
    if (diet === "gluten_free" && allergens.has("en:gluten")) notes.diets.push("Contains gluten");
    else if (diet === "gluten_free" && traces.has("en:gluten")) notes.diets.push("May contain gluten");
  }
  return notes;
}
