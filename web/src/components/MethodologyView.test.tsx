import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Methodology } from "@/lib/api";
import { loadMethodology } from "@/lib/api";
import AboutPage from "@/app/about/page";

import { MethodologyView } from "./MethodologyView";
import { ProductFooter } from "./ProductView";

const M: Methodology = {
  engine_version: "0.3.0",
  weights: { nutrition: 60, additives: 30, processing: 10 },
  bands: [
    { id: "excellent", label: "Excellent", min: 75 }, { id: "good", label: "Good", min: 50 },
    { id: "mediocre", label: "Mediocre", min: 25 }, { id: "poor", label: "Poor", min: 0 },
  ],
  nova_values: { "1": 1, "2": 0.67, "3": 0.33, "4": 0 },
  additives: { risk_penalty: { "0": 0, "1": 0.05, "2": 0.15, "3": 0.4 }, evidence_weight: { A: 1, B: 0.6, C: 0.3 }, cap_total: 49 },
  sources: { nutriscore_foods: "https://ns.test/foods", nutriscore_beverages: "https://ns.test/drinks", efsa: "https://efsa.test", nova: "https://nova.test" },
  changelog: [{ version: "0.1.0", change: "First." }, { version: "0.3.0", change: "Water fix (`NS-22`)." }],
};

describe("[METH-3] the score explained with the API's numbers", () => {
  it("shows the formula, bands and anchored component sections", () => {
    const { container } = render(<MethodologyView m={M} />);
    expect(container).toHaveTextContent("60·N + 30·A + 10·P");
    expect(screen.getByRole("row", { name: "75–100 Excellent" })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: "25–49 Mediocre" })).toBeInTheDocument();
    for (const id of ["nutrition", "additives", "processing"]) {
      expect(container.querySelector(`section#${id}`)).not.toBeNull();
    }
    expect(screen.getByRole("region", { name: "Additives (30 points)" })).toHaveTextContent("caps the whole score at 49");
    expect(screen.getByRole("region", { name: "Processing (10 points)" })).toHaveTextContent("ultra-processed 0%");
  });
});

describe("[METH-4] missing data, estimates and sources", () => {
  it("explains rescaling, not scored, estimates and the golden gate, with source links", () => {
    render(<MethodologyView m={M} />);
    expect(screen.getByRole("region", { name: "Missing data" })).toHaveTextContent("We never guess a nutrient");
    expect(screen.getByText(/match 99.27%/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "drinks" })).toHaveAttribute("href", "https://ns.test/drinks");
    expect(screen.getByRole("link", { name: "About NOVA" })).toHaveAttribute("href", "https://nova.test");
  });
});

describe("[METH-5] changelog and an unreachable API", () => {
  it("lists versions newest first", () => {
    render(<MethodologyView m={M} />);
    const items = screen.getByRole("region", { name: "Changes to the scoring" }).querySelectorAll("li");
    expect([...items].map((li) => li.textContent)).toEqual(["0.3.0: Water fix (NS-22).", "0.1.0: First."]);
  });

  it("says the details are unavailable instead of showing numbers", () => {
    render(<MethodologyView m={null} />);
    expect(screen.getByRole("status")).toHaveTextContent("aren't available right now");
  });

  it("loads from the API and returns null on failure", async () => {
    expect(await loadMethodology(vi.fn(async () => Response.json(M)))).toEqual(M);
    expect(await loadMethodology(vi.fn(async () => new Response(null, { status: 500 })))).toBeNull();
  });
});

describe("[METH-6] about page", () => {
  it("credits every data source with its license and says it's not medical advice", () => {
    render(<AboutPage />);
    for (const name of ["Open Food Facts", "USDA FoodData Central", "openFDA", "FDA Substances Added to Food"]) {
      expect(screen.getByRole("link", { name })).toBeInTheDocument();
    }
    expect(screen.getByText(/Open Database License \(ODbL\)/)).toBeInTheDocument();
    expect(screen.getByText(/AI-Powered Grocery Intelligence Platform/)).toBeInTheDocument();
    expect(screen.getByText(/not medical advice/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "FoodTrace on GitHub" })).toHaveAttribute("href", "https://github.com/samarthshete/FoodTrace");
  });
});

describe("[METH-7] site footer", () => {
  it("shows the FoodTrace brand and links Methodology, About and Privacy", () => {
    render(<ProductFooter />);
    expect(screen.getByText("FT")).toBeInTheDocument();
    expect(screen.getByText("FoodTrace")).toBeInTheDocument();
    expect(screen.getByText("AI-Powered Grocery Intelligence Platform")).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Site" });
    expect(nav).toContainElement(screen.getByRole("link", { name: "How the score works" }));
    expect(screen.getByRole("link", { name: "About" })).toHaveAttribute("href", "/about");
    expect(screen.getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/privacy");
  });
});
