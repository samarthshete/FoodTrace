import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Alternatives, Breakdown, Product } from "@/lib/api";
import scored from "@/test/fixtures/scored.json";

import { AlternativesStrip } from "./AlternativesStrip";
import { ProductView } from "./ProductView";

const DATA: Alternatives = {
  gtin: "0036000291452",
  category: "en:cereal-bars",
  alternatives: [
    {
      gtin: "0000000000017",
      name: "Plain Oat Bars",
      brand: "Good Grain",
      image_url: "https://images.test/plain.jpg",
      total: 82,
      band: { id: "excellent", label: "Excellent" },
      confidence: 1,
    },
    {
      gtin: "0000000000024",
      name: null,
      brand: null,
      image_url: null,
      total: 61,
      band: { id: "good", label: "Good" },
      confidence: 0.9,
    },
  ],
};

describe("[ALT-10] alternatives strip", () => {
  it("shows each alternative's name, brand, score and band in words, linking to its page", () => {
    render(<AlternativesStrip data={DATA} />);
    const strip = screen.getByRole("region", { name: "Better-scored alternatives" });
    const links = within(strip).getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "/p/0000000000017");
    expect(links[0]).toHaveTextContent("Plain Oat Bars");
    expect(links[0]).toHaveTextContent("Good Grain");
    expect(links[0]).toHaveTextContent("82 / 100 · Excellent");
    expect(links[1]).toHaveTextContent("Unnamed product");
    expect(links[1]).toHaveTextContent("61 / 100 · Good");
  });

  it("sits below the score summary on the product page", () => {
    const { product, breakdown } = scored as unknown as { product: Product; breakdown: Breakdown };
    render(<ProductView product={product} breakdown={breakdown} alternatives={DATA} />);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings.indexOf("Better-scored alternatives")).toBe(headings.indexOf("In short") + 1);
  });
});

describe("[ALT-11] empty or failed alternatives", () => {
  it.each([
    ["an empty list", { ...DATA, alternatives: [] }],
    ["a failed request", null],
  ])("hides the strip for %s", (_, data) => {
    render(<AlternativesStrip data={data} />);
    expect(screen.queryByRole("region", { name: "Better-scored alternatives" })).toBeNull();
  });
});

describe("[ALT-12] category in words", () => {
  it("names the matched category", () => {
    render(<AlternativesStrip data={DATA} />);
    expect(screen.getByText("In cereal bars")).toBeInTheDocument();
  });
});
