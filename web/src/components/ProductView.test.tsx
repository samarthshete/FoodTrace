import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Breakdown, Product } from "@/lib/api";
import notScored from "@/test/fixtures/not_scored.json";
import rescaled from "@/test/fixtures/rescaled.json";
import scored from "@/test/fixtures/scored.json";

import { ProductFooter, ProductMessage, ProductView } from "./ProductView";

// Fixtures are generated from the real Python engine (see web/src/test/fixtures).
type Fixture = { product: Product; breakdown: Breakdown };

function renderFixture(f: unknown) {
  const { product, breakdown } = f as Fixture;
  return render(<ProductView product={product} breakdown={breakdown} />);
}

describe("[PAGE-1] score and band", () => {
  it("shows the total out of 100 and the band label in text", () => {
    renderFixture(scored);
    expect(screen.getByText("49")).toBeInTheDocument();
    expect(screen.getByText("/ 100")).toBeInTheDocument();
    expect(screen.getByText("Mediocre")).toBeInTheDocument();
  });
});

describe("[PAGE-2] component bars", () => {
  it("shows points out of each weight", () => {
    renderFixture(scored);
    const section = screen.getByRole("region", { name: "What makes up the score" });
    expect(within(section).getByText("Nutrition").nextSibling).toHaveTextContent("36.7 of 60");
    expect(within(section).getByText("Processing").nextSibling).toHaveTextContent("0 of 10");
  });

  it("shows No data for an unknown component and explains the rescale", () => {
    renderFixture(rescaled);
    const section = screen.getByRole("region", { name: "What makes up the score" });
    expect(within(section).getByText("Processing").nextSibling).toHaveTextContent("No data");
    expect(section).toHaveTextContent("worked out from the parts we have");
  });
});

describe("[PAGE-3] Nutri-Score grade", () => {
  it("shows the grade letter and the class", () => {
    renderFixture(rescaled);
    expect(screen.getByText(/Nutri-Score C, scored as a drink/)).toBeInTheDocument();
  });
});

describe("[PAGE-4] explanation", () => {
  it("lists the API's sentences", () => {
    renderFixture(scored);
    const section = screen.getByRole("region", { name: "In short" });
    for (const sentence of (scored as unknown as Fixture).breakdown.explanation) {
      expect(within(section).getByText(sentence)).toBeInTheDocument();
    }
  });
});

describe("[PAGE-5] breakdown lines", () => {
  it("groups lines by component with value, points and a source link", () => {
    renderFixture(scored);
    const section = screen.getByRole("region", { name: "Every rule applied" });
    const sugars = within(section).getByText("Sugars").closest("li")!;
    expect(sugars).toHaveTextContent("12 g");
    expect(sugars).toHaveTextContent("+3");
    expect(within(sugars).getByRole("link", { name: "Source for Sugars" })).toHaveAttribute(
      "href",
      expect.stringContaining("https://"),
    );
    expect(within(section).getByRole("heading", { name: "Additives" })).toBeInTheDocument();
  });

  it("marks estimated lines", () => {
    renderFixture(scored);
    const fvl = screen.getByText("Fruit, vegetables and legumes").closest("li")!;
    expect(within(fvl).getByText("Estimated")).toBeInTheDocument();
  });

  it("does not show the component summary lines as rules", () => {
    renderFixture(scored);
    expect(screen.queryByText(/component\./)).toBeNull();
  });
});

describe("[PAGE-6] additives", () => {
  it("shows the EFSA rating in words, and Not rated for unrated additives", () => {
    renderFixture(scored);
    const nitrite = screen.getByText("E250 - Sodium nitrite").closest("li")!;
    expect(nitrite).toHaveTextContent("High estimated overexposure risk (EFSA)");
    const citric = screen.getByText("E330 - Citric acid").closest("li")!;
    expect(citric).toHaveTextContent("Not rated by EFSA");
  });

  it("does not repeat the rating as a second note", () => {
    renderFixture(scored);
    const nitrite = screen.getByText("E250 - Sodium nitrite").closest("li")!;
    expect(nitrite.textContent!.match(/overexposure risk/gi)).toHaveLength(1);
    const nova = screen.getByText("Processing (NOVA)").closest("li")!;
    expect(nova.textContent!.match(/ultra-processed/g)).toHaveLength(1);
  });
});

describe("[PAGE-7] data badge", () => {
  it("labels confidence and lists missing inputs in words", () => {
    renderFixture(rescaled);
    expect(screen.getByText("Partial data")).toBeInTheDocument(); // 8 of 9 inputs = 0.89
    expect(screen.getByText("Missing: processing level.")).toBeInTheDocument();
  });

  it("shows Complete data when every input is present", () => {
    const f = structuredClone(scored) as unknown as Fixture;
    f.product.score.confidence = 1;
    render(<ProductView product={f.product} breakdown={f.breakdown} />);
    expect(screen.getByText("Complete data")).toBeInTheDocument();
  });

  it("shows Limited data for low confidence", () => {
    renderFixture(notScored);
    expect(screen.getByText("Limited data")).toBeInTheDocument();
  });
});

describe("[PAGE-8] ingredients", () => {
  it("shows ingredients when present and omits the section otherwise", () => {
    const { unmount } = renderFixture(scored);
    expect(screen.getByRole("region", { name: "Ingredients" })).toHaveTextContent("Oats, sugar");
    unmount();
    renderFixture(notScored);
    expect(screen.queryByRole("region", { name: "Ingredients" })).toBeNull();
  });
});

describe("[PAGE-9] not scored", () => {
  it("says Not scored and why, and still shows additives and processing", () => {
    renderFixture(notScored);
    expect(screen.getByText("Not scored")).toBeInTheDocument();
    expect(screen.getByText(/The label data is missing sugars, saturated fat/)).toBeInTheDocument();
    expect(screen.getByText("E338 - Phosphoric acid")).toBeInTheDocument();
    expect(screen.getByText("Processing (NOVA)")).toBeInTheDocument();
    expect(screen.queryByText("/ 100")).toBeNull();
  });
});

describe("[PAGE-10] stale data", () => {
  it("shows a notice when the data couldn't be refreshed", () => {
    renderFixture(rescaled);
    expect(screen.getByRole("status")).toHaveTextContent("Showing saved data");
  });

  it("shows no notice for fresh data", () => {
    renderFixture(scored);
    expect(screen.queryByRole("status")).toBeNull();
  });
});

describe("[PAGE-11] error states render a message and a way back", () => {
  it("renders a title, body and a link to scan again", () => {
    render(<ProductMessage title="We couldn't find this product" body="Not in the database." />);
    expect(screen.getByRole("heading", { name: "We couldn't find this product" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Scan or type another barcode" })).toHaveAttribute(
      "href",
      "/lookup",
    );
  });
});

describe("[PAGE-12] footer", () => {
  it("attributes Open Food Facts and says it is not medical advice", () => {
    render(<ProductFooter />);
    expect(screen.getByRole("link", { name: "Open Food Facts (ODbL)" })).toHaveAttribute(
      "href",
      "https://world.openfoodfacts.org",
    );
    expect(screen.getByText("Educational information, not medical advice.")).toBeInTheDocument();
  });
});

describe("[PAGE-15] rounded input values", () => {
  it("shows kJ whole and grams to one decimal", () => {
    const f = structuredClone(scored) as unknown as Fixture;
    const line = f.breakdown.score.breakdown.find((l) => l.rule_id === "nutriscore.general.sugars")!;
    line.input_value = 20.354;
    const energy = f.breakdown.score.breakdown.find((l) => l.rule_id === "nutriscore.general.energy")!;
    energy.input_value = 1009.73;
    render(<ProductView product={f.product} breakdown={f.breakdown} />);
    expect(screen.getByText("Sugars").closest("li")).toHaveTextContent("20.4 g");
    expect(screen.getByText("Energy").closest("li")).toHaveTextContent("1010 kJ");
  });
});

describe("[PAGE-16] empty components say why", () => {
  it("says no additives were found when the ingredient list has none", () => {
    const f = structuredClone(scored) as unknown as Fixture;
    f.breakdown.score.breakdown = f.breakdown.score.breakdown.filter(
      (l) => l.component !== "additives" || l.rule_id.startsWith("component."),
    );
    render(<ProductView product={f.product} breakdown={f.breakdown} />);
    expect(screen.getByText("No additives found in the ingredient list.")).toBeInTheDocument();
  });

  it("says No data when the component is unknown", () => {
    renderFixture(rescaled); // processing unknown
    const section = screen.getByRole("region", { name: "Every rule applied" });
    expect(within(section).getByText("No data.")).toBeInTheDocument();
  });
});

describe("[FDA-6] US status of additives", () => {
  it("states the FDA status in words with a link to the CFR section", () => {
    const f = structuredClone(scored) as unknown as Fixture;
    f.product.additives = [
      { code: "e250", name: "E250 - Sodium nitrite", us_status: "food_additive", fda_cfr_ref: "172.170" },
      { code: "e330", name: "E330 - Citric acid", us_status: null, fda_cfr_ref: null },
    ];
    render(<ProductView product={f.product} breakdown={f.breakdown} />);
    const nitrite = screen.getByText("E250 - Sodium nitrite").closest("li")!;
    expect(nitrite).toHaveTextContent("US: approved food additive (21 CFR 172.170)");
    expect(within(nitrite).getByRole("link", { name: "21 CFR 172.170" })).toHaveAttribute(
      "href",
      "https://www.ecfr.gov/current/title-21/section-172.170",
    );
    const citric = screen.getByText("E330 - Citric acid").closest("li")!;
    expect(citric).not.toHaveTextContent("US:");
  });

  it.each([
    ["color_additive", "74.303", "US: approved color additive (21 CFR 74.303)"],
    ["gras", "184.1033", "US: generally recognized as safe, GRAS (21 CFR 184.1033)"],
    ["prior_sanctioned", "181.33", "US: prior-sanctioned (21 CFR 181.33)"],
    ["prohibited", "189.120", "US: prohibited in food (21 CFR 189.120)"],
    ["gras_flavor", null, "US: flavoring, GRAS per FEMA"],
    ["delisted", null, "US: color listing ended (delisted)"],
  ])("words %s", (status, cfr, words) => {
    const f = structuredClone(scored) as unknown as Fixture;
    f.product.additives = [
      { code: "e250", name: "E250 - Sodium nitrite", us_status: status, fda_cfr_ref: cfr },
    ];
    render(<ProductView product={f.product} breakdown={f.breakdown} />);
    expect(screen.getByText("E250 - Sodium nitrite").closest("li")).toHaveTextContent(words);
  });
});

describe("[PAGE-17] full additive marks are explained", () => {
  it("says none of the additives has an EFSA risk rating", () => {
    const f = structuredClone(scored) as unknown as Fixture;
    f.product.score.components.additives = { weight: 30, value: 1, known: true };
    f.product.additives = [
      { code: "e322", name: "E322 - Lecithins", us_status: "gras", fda_cfr_ref: "184.1400" },
      { code: "e414", name: "E414 - Acacia gum", us_status: null, fda_cfr_ref: null },
    ];
    render(<ProductView product={f.product} breakdown={f.breakdown} />);
    const bars = screen.getByRole("region", { name: "What makes up the score" });
    expect(bars).toHaveTextContent("None of its 2 additives has an EFSA risk rating.");
  });

  it("says nothing when there are no additives or some were rated", () => {
    const f = structuredClone(scored) as unknown as Fixture;
    f.product.additives = [];
    render(<ProductView product={f.product} breakdown={f.breakdown} />);
    expect(screen.queryByText(/EFSA risk rating\./)).toBeNull();
  });
});
