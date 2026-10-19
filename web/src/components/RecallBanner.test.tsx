import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Breakdown, Product, Recall, Recalls } from "@/lib/api";
import scored from "@/test/fixtures/scored.json";

import { ProductView } from "./ProductView";
import { RecallBanner } from "./RecallBanner";

const URL = "https://api.fda.gov/food/enforcement.json?search=recall_number:%22F-1-2026%22";

function recall(overrides: Partial<Recall> = {}): Recall {
  return {
    recall_number: "F-1-2026",
    match: "brand_name",
    classification: "Class II",
    status: "Ongoing",
    reason_for_recall: "Undeclared peanut",
    recall_initiation_date: "2026-08-01",
    product_description: "Acme Foods Crunchy Oat Bars",
    url: URL,
    ...overrides,
  };
}

function data(recalls: Recall[], as_of: string | null = "2026-10-12T06:00:00+00:00"): Recalls {
  return { gtin: "0036000291452", recalls, as_of };
}

describe("[RECALL-12] banner content", () => {
  it("shows the heading, FDA's reason, start date and a link to the record", () => {
    render(<RecallBanner data={data([recall()])} />);
    expect(screen.getByRole("heading", { name: "A related FDA recall is on record" })).toBeVisible();
    expect(screen.getByText("Reason given by the FDA: Undeclared peanut")).toBeInTheDocument();
    expect(screen.getByText("Recall started Aug 1, 2026.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View the FDA record" })).toHaveAttribute("href", URL);
    expect(screen.queryByText(/more on record/)).toBeNull();
  });

  it("says the barcode is listed for a code match, and counts the rest", () => {
    render(<RecallBanner data={data([recall({ match: "code" }), recall(), recall()])} />);
    expect(
      screen.getByRole("heading", { name: "An FDA recall on record lists this barcode" }),
    ).toBeVisible();
    expect(screen.getByText("And 2 more on record.")).toBeInTheDocument();
  });

  it("sits above the score on the product page", () => {
    const { product, breakdown } = scored as unknown as { product: Product; breakdown: Breakdown };
    render(<ProductView product={product} breakdown={breakdown} recalls={data([recall()])} />);
    const banner = screen.getByRole("status");
    const score = screen.getByText("/ 100");
    expect(banner.compareDocumentPosition(score) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

describe("[RECALL-13] careful wording", () => {
  it("never says the product is recalled, hedges brand matches and dates the data", () => {
    const { container } = render(<RecallBanner data={data([recall()])} />);
    expect(container.textContent).not.toMatch(/is recalled|unsafe|dangerous/i);
    expect(
      screen.getByText("This may be a different product from the same brand."),
    ).toBeInTheDocument();
    expect(screen.getByText("FDA data as of Oct 12, 2026.")).toBeInTheDocument();
  });

  it("drops the hedge for a code match", () => {
    render(<RecallBanner data={data([recall({ match: "code" })])} />);
    expect(screen.queryByText(/different product/)).toBeNull();
  });
});

describe("[RECALL-14] no banner without data", () => {
  it.each([
    ["no records", data([])],
    ["data never synced", data([recall()], null)],
    ["a failed request", null],
  ])("renders nothing for %s", (_, value) => {
    const { container } = render(<RecallBanner data={value} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("[RECALL-15] accessible banner", () => {
  it("is a status region with a text heading and a non-colour marker", () => {
    render(<RecallBanner data={data([recall()])} />);
    const banner = screen.getByRole("status");
    expect(banner).toHaveAccessibleName("A related FDA recall is on record");
    expect(banner).toHaveTextContent("⚠");
  });
});
