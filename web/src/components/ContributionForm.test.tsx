import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Breakdown, Product } from "@/lib/api";
import { fitWithin } from "@/lib/ocr";
import scored from "@/test/fixtures/scored.json";

import { ContributionForm } from "./ContributionForm";
import { ProductMessage, ProductView } from "./ProductView";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const LABEL = `Serving size 2/3 cup (55g)
Calories 230
Total Fat 8g
Saturated Fat 1g
Sodium 160mg
Total Sugars 12g
Protein 3g`;

function fetcherWith(canShare: boolean, saveStatus = 201, saveBody: unknown = {}) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (String(input) === "/api/contributions/config") return Response.json({ can_share_with_off: canShare });
    return Response.json(saveBody, { status: saveStatus, headers: init?.headers });
  });
}

async function readPhoto(readText: () => Promise<string>) {
  const fetcher = fetcherWith(false);
  render(<ContributionForm gtin="0000000000017" readText={readText} fetcher={fetcher} />);
  const photo = screen.getByLabelText("Photo of the Nutrition Facts panel");
  fireEvent.change(photo, { target: { files: [new File(["x"], "label.jpg", { type: "image/jpeg" })] } });
  return fetcher;
}

beforeEach(() => push.mockReset());

describe("[CONTRIB-1] reading the label in the browser", () => {
  it("shrinks photos to at most 1600 px on the long side, never enlarging", () => {
    expect(fitWithin(4032, 3024)).toEqual({ width: 1600, height: 1200 });
    expect(fitWithin(1000, 3000)).toEqual({ width: 533, height: 1600 });
    expect(fitWithin(800, 600)).toEqual({ width: 800, height: 600 });
  });

  it("the not-found page offers to add the product from a photo", () => {
    render(
      <ProductMessage
        title="We couldn't find this product"
        body="Not found."
        action={{ href: "/add/0000000000017", label: "Add it from a label photo" }}
      />,
    );
    expect(screen.getByRole("link", { name: "Add it from a label photo" })).toHaveAttribute(
      "href",
      "/add/0000000000017",
    );
  });
});

describe("[CONTRIB-3] the user checks every value before saving", () => {
  it("pre-fills per-100 g values from the photo and says to check them", async () => {
    await readPhoto(async () => LABEL);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Read 6 of 7 values"));
    expect(screen.getByLabelText("Energy (kJ)")).toHaveValue(1750);
    expect(screen.getByLabelText("Salt (g)")).toHaveValue(0.727);
    expect(screen.getByLabelText("Fibre (g), optional")).toHaveValue(null);
  });

  it("requires the four values needed to score, and saves nothing until confirmed", async () => {
    const fetcher = await readPhoto(async () => "unreadable");
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("couldn't read"));
    for (const label of ["Energy (kJ)", "Sugars (g)", "Saturated fat (g)", "Salt (g)"]) {
      expect(screen.getByLabelText(label)).toBeRequired();
    }
    expect(screen.getByLabelText("Protein (g), optional")).not.toBeRequired();
    expect(fetcher).not.toHaveBeenCalledWith("/api/contributions", expect.anything());
  });

  it("posts the confirmed fields and opens the scored product", async () => {
    const fetcher = await readPhoto(async () => LABEL);
    await waitFor(() => expect(screen.getByLabelText("Energy (kJ)")).toHaveValue(1750));
    fireEvent.change(screen.getByLabelText("Product name"), { target: { value: "Granola" } });
    fireEvent.change(screen.getByLabelText("What is it?"), { target: { value: "drink" } });
    fireEvent.submit(screen.getByRole("button", { name: "Save and score" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/p/0000000000017"));
    const [, init] = fetcher.mock.calls.find(([url]) => String(url) === "/api/contributions")!;
    const sent = JSON.parse(String(init!.body));
    expect(sent).toMatchObject({ gtin: "0000000000017", name: "Granola", kind: "drink",
      share_with_off: false, nutrition: { energy_kj: 1750, salt_g: 0.727 } });
    expect(sent.nutrition.fiber_g).toBeUndefined();
  });

  it("explains a product someone already added", async () => {
    const fetcher = fetcherWith(false, 409);
    render(<ContributionForm gtin="0000000000017" readText={async () => LABEL} fetcher={fetcher} />);
    fireEvent.submit(screen.getByRole("button", { name: "Save and score" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already added");
  });
});

describe("[CONTRIB-7] contributed products are marked", () => {
  it("says a user added it and it isn't checked yet", () => {
    const { product, breakdown } = structuredClone(scored) as unknown as {
      product: Product;
      breakdown: Breakdown;
    };
    product.source_by_field = { name: "contribution", nutrition: "contribution" };
    render(<ProductView product={product} breakdown={breakdown} />);
    expect(screen.getByText("Added by a user from a label photo. Not yet checked.")).toBeVisible();
  });
});

describe("[CONTRIB-9] sharing with Open Food Facts is opt-in", () => {
  it("shows an unticked checkbox only when the server can share", async () => {
    render(<ContributionForm gtin="0000000000017" fetcher={fetcherWith(true)} />);
    const box = await screen.findByRole("checkbox", { name: /Also add it to Open Food Facts/ });
    expect(box).not.toBeChecked();
  });

  it("hides it otherwise", async () => {
    const fetcher = fetcherWith(false);
    render(<ContributionForm gtin="0000000000017" fetcher={fetcher} />);
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(screen.queryByRole("checkbox")).toBeNull();
  });
});
