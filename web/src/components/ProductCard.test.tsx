import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ExploreItem } from "@/lib/explore";

import { ProductCard, ProductCardSkeleton } from "./ProductCard";

const ITEM: ExploreItem = {
  gtin: "0076808008470", name: "Red Lentil Rotini", brand: "Barilla", image_url: "https://img/x.jpg",
  total: 97, band: { id: "excellent", label: "Excellent" }, nutriscore_grade: "a", nova_group: 1,
};

describe("[EXPLORE-6] product cards", () => {
  it("shows rank, score, band, Nutri-Score and NOVA, and links to the product", () => {
    render(<ProductCard item={ITEM} rank={1} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/p/0076808008470");
    expect(link).toHaveTextContent("#1");
    expect(link).toHaveTextContent("97 out of 100");
    expect(link).toHaveTextContent("Excellent");
    expect(link).toHaveTextContent("Nutri-Score A");
    expect(link).toHaveTextContent("NOVA 1");
    expect(link).toHaveTextContent("Barilla");
  });

  it("copes with missing image, brand, grade and NOVA", () => {
    render(<ProductCard item={{ ...ITEM, image_url: null, brand: null, nutriscore_grade: null, nova_group: null }} />);
    const link = screen.getByRole("link");
    expect(link).not.toHaveTextContent("Nutri-Score");
    expect(link).not.toHaveTextContent("NOVA");
    expect(link).not.toHaveTextContent("#");
    expect(link.querySelector("img")).toBeNull();
  });

  it("has a hidden loading skeleton", () => {
    const { container } = render(<ProductCardSkeleton />);
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });
});
