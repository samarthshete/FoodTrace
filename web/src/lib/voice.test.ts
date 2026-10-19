import { describe, expect, it } from "vitest";

import type { Alternatives, Breakdown, Product } from "./api";
import scored from "@/test/fixtures/scored.json";
import notScored from "@/test/fixtures/not_scored.json";

import { HELP, answer, intentOf, summary } from "./voice";

type Fixture = { product: Product; breakdown: Breakdown };
const page = (f: unknown, extra: Partial<Product> = {}, alternatives: Alternatives | null = null) => {
  const { product, breakdown } = structuredClone(f) as Fixture;
  return { product: { ...product, ...extra }, breakdown, alternatives };
};
const BANNED = /\b(safe|toxic|dangerous|unsafe)\b/i;

describe("[VOICE-1] intents by keyword, first match wins", () => {
  it.each([
    ["Does it contain milk?", "allergen"],
    ["Is there gluten in this", "allergen"],
    ["What's a healthier alternative?", "alternatives"],
    ["Why is the score low?", "why"],
    ["Any preservatives?", "additives"],
    ["How healthy is it", "score"],
    ["Read it to me", "summary"],
    ["What's the weather", "help"],
  ])("%s → %s", (q, intent) => {
    expect(intentOf(q)).toBe(intent);
  });
});

describe("[VOICE-2] answers come from the page's data", () => {
  it("states the score and band", () => {
    expect(answer("what's the score?", page(scored))).toMatch(/scores 49 out of 100, which is Mediocre/);
  });

  it("explains why with the page's sentences, and lists additives", () => {
    const data = page(scored);
    expect(answer("why?", data)).toBe(data.breakdown.explanation.slice(1).join(" "));
    expect(answer("any additives?", data)).toMatch(/E250 - Sodium nitrite/);
  });

  it("names up to three better-scored alternatives, or says there are none", () => {
    const alts: Alternatives = { gtin: "x", category: "en:snacks", alternatives: [
      { gtin: "1", name: "Plain Oat Bars", brand: null, image_url: null, total: 82, band: null, confidence: 1 },
    ] };
    expect(answer("something healthier?", page(scored, {}, alts))).toBe(
      "Better-scored options in the same category: Plain Oat Bars, 82 out of 100.",
    );
    expect(answer("something healthier?", page(scored))).toMatch(/don't have better-scored alternatives/);
  });

  it("says a not-scored product isn't scored", () => {
    expect(answer("score?", page(notScored))).toMatch(/isn't scored: the label data is incomplete/);
  });

  it("reads a summary aloud: the score then the explanation", () => {
    const data = page(scored);
    expect(summary(data)).toMatch(/^.* scores 49 out of 100/);
    expect(answer("read it", data)).toBe(summary(data));
  });
});

describe("[VOICE-3] allergens from the label only, never 'safe'", () => {
  const labelled = { allergens: ["en:milk", "en:gluten"], allergens_known: true };

  it("says what the label lists or doesn't list", () => {
    expect(answer("does it contain dairy or soy?", page(scored, labelled))).toBe(
      "The label lists milk. The label doesn't list soybeans.",
    );
    expect(answer("any gluten?", page(scored, labelled))).toBe("The label lists wheat.");
    expect(answer("what allergens?", page(scored, labelled))).toBe("The label lists milk, wheat.");
  });

  it("says when allergen data isn't available", () => {
    expect(answer("contains nuts?", page(scored, { allergens_known: false }))).toBe(
      "Allergen information isn't available for this product. Check the label.",
    );
  });

  it("never uses banned words in any answer", () => {
    const qs = ["score", "why", "additives", "contains milk", "alternatives", "read", "hello"];
    for (const q of qs) expect(answer(q, page(scored, labelled))).not.toMatch(BANNED);
  });
});

describe("[VOICE-4] help", () => {
  it("explains what can be asked", () => {
    expect(answer("hello", page(scored))).toBe(HELP);
  });
});
