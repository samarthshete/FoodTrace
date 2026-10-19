import { describe, expect, it } from "vitest";

import { type Preferences, personalNotes } from "./allergens";

const prefs = (p: Partial<Preferences>): Preferences => ({ allergens: [], diets: [], save_history: true, ...p });
const label = { allergens: ["en:milk", "en:gluten"], traces: ["en:nuts"],
  ingredients_analysis: ["en:non-vegan", "en:vegetarian"], allergens_known: true };

describe("[ACC-7] allergen and diet notes", () => {
  it("lists the user's allergens the product contains or may contain", () => {
    const notes = personalNotes(label, prefs({ allergens: ["milk", "tree_nuts", "sesame", "wheat"] }));
    expect(notes.contains).toEqual(["Milk", "Wheat"]);
    expect(notes.mayContain).toEqual(["Tree nuts"]);
    expect(notes.unknown).toBe(false);
  });

  it("notes diets the product doesn't meet", () => {
    const notes = personalNotes(label, prefs({ diets: ["vegan", "vegetarian", "gluten_free"] }));
    expect(notes.diets).toEqual(["Not vegan", "Contains gluten"]);
  });

  it("says the data is unknown rather than implying it's fine", () => {
    const notes = personalNotes({ allergens: [], allergens_known: false }, prefs({ allergens: ["milk"] }));
    expect(notes).toEqual({ unknown: true, contains: [], mayContain: [], diets: [] });
  });

  it("says nothing to users without allergens or diets", () => {
    expect(personalNotes(label, prefs({}))).toEqual({ unknown: false, contains: [], mayContain: [], diets: [] });
  });
});
