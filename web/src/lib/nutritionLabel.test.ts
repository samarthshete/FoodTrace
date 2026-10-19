import { describe, expect, it } from "vitest";

import { parseLabel } from "./nutritionLabel";

// Text as Tesseract reads a typical US panel, slips included ("Og", split decimals).
const PANEL = `Nutrition Facts
8 servings per container
Serving size 2/3 cup (55g)
Amount per serving
Calories 230
% Daily Value*
Total Fat 8g 10%
Saturated Fat 1g 5%
Trans Fat Og
Cholesterol Omg 0%
Sodium 160mg 7%
Total Carbohydrate 37g 13%
Dietary Fiber 4g 14%
Total Sugars 12g
Includes 10g Added Sugars 20%
Protein 3g`;

describe("[CONTRIB-2] Nutrition Facts parsing", () => {
  it("reads per-serving values and the serving size", () => {
    const { servingG, perServing } = parseLabel(PANEL);
    expect(servingG).toBe(55);
    expect(perServing).toEqual({
      calories: 230, fat_g: 8, saturated_fat_g: 1, sodium_mg: 160, carbohydrate_g: 37,
      fiber_g: 4, sugars_g: 12, proteins_g: 3,
    });
  });

  it("converts to per 100 g: kcal to kJ and sodium to salt", () => {
    const { per100g } = parseLabel(PANEL);
    expect(per100g.energy_kj).toBe(1750); // 230 kcal × 4.184 × 100/55
    expect(per100g.sugars_g).toBe(21.82);
    expect(per100g.salt_g).toBe(0.727); // 160 mg × 2.5 / 1000 × 100/55
    expect(per100g.saturated_fat_g).toBe(1.82);
  });

  it("does not take added sugars as total sugars", () => {
    const { perServing } = parseLabel("Serving size 30g\nIncludes 10g Added Sugars\nTotal Sugars 12g");
    expect(perServing.sugars_g).toBe(12);
  });

  it("leaves unreadable fields empty and converts nothing without a serving size", () => {
    const { servingG, perServing, per100g } = parseLabel("Calories 120\nProtein 3g");
    expect(servingG).toBeUndefined();
    expect(perServing).toEqual({ calories: 120, proteins_g: 3 });
    expect(per100g).toEqual({});
  });

  it("reads millilitre servings for drinks", () => {
    const { servingG, per100g } = parseLabel("Serving size 1 can (355 mL)\nCalories 140\nTotal Sugars 39g");
    expect(servingG).toBe(355);
    expect(per100g.sugars_g).toBe(10.99);
  });
});
