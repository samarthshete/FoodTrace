import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProductAccount } from "./ProductAccount";

const session = vi.hoisted(() => ({ value: null as null | { user: { name: string } } }));
vi.mock("@/lib/auth-client", () => ({ useSession: () => ({ data: session.value, isPending: false }) }));

const GTIN = "0036000291452";
const LABEL = { allergens: ["en:milk"], traces: [], ingredients_analysis: [], allergens_known: true };

function api(prefs = { allergens: ["milk"], diets: [], save_history: true }, favorites: string[] = []) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/me") return Response.json({ preferences: prefs });
    if (url === "/api/me/favorites") return Response.json({ items: favorites.map((gtin) => ({ gtin })) });
    if (url === "/api/me/history") return Response.json({ saved: true }, { status: 201 });
    return new Response(null, { status: init?.method === "PUT" || init?.method === "DELETE" ? 204 : 404 });
  });
}

beforeEach(() => {
  session.value = { user: { name: "Alice" } };
});

describe("[ACC-9] saving the view to history", () => {
  it("records the product once for a signed-in user", async () => {
    const fetcher = api();
    render(<ProductAccount gtin={GTIN} label={LABEL} fetcher={fetcher} />);
    await waitFor(() => expect(fetcher).toHaveBeenCalledWith("/api/me/history", expect.anything()));
    const [, init] = fetcher.mock.calls.find(([u]) => String(u) === "/api/me/history")!;
    expect(JSON.parse(String(init!.body))).toEqual({ gtin: GTIN });
  });

  it("does nothing when signed out", () => {
    session.value = null;
    const fetcher = api();
    const { container } = render(<ProductAccount gtin={GTIN} label={LABEL} fetcher={fetcher} />);
    expect(container).toBeEmptyDOMElement();
    expect(fetcher).not.toHaveBeenCalled();
  });
});

describe("[ACC-7] [ACC-8] warnings on the product page", () => {
  it("warns about the user's allergens, from the label, linking to the ingredients", async () => {
    render(<ProductAccount gtin={GTIN} label={LABEL} fetcher={api()} />);
    const warning = await screen.findByRole("region", { name: /For your allergens and diet/ });
    expect(warning).toHaveTextContent("Contains: Milk");
    expect(warning).toHaveTextContent("From the label data.");
    expect(screen.getByRole("link", { name: "Read the ingredients" })).toHaveAttribute("href", "#ingredients-heading");
    expect(warning.textContent).not.toMatch(/\bsafe\b/i);
  });

  it("shows no warning when nothing matches", async () => {
    const fetcher = api({ allergens: ["sesame"], diets: [], save_history: true });
    render(<ProductAccount gtin={GTIN} label={LABEL} fetcher={fetcher} />);
    await waitFor(() => expect(fetcher).toHaveBeenCalledWith("/api/me"));
    expect(screen.queryByRole("region")).toBeNull();
  });
});

describe("[ACC-12] Save toggle", () => {
  it("shows saved state and toggles with PUT and DELETE", async () => {
    const fetcher = api(undefined, [GTIN]);
    render(<ProductAccount gtin={GTIN} label={LABEL} fetcher={fetcher} />);
    const button = await screen.findByRole("button", { name: "★ Saved" });
    expect(button).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(button);
    await waitFor(() => expect(fetcher).toHaveBeenCalledWith(`/api/me/favorites/${GTIN}`, { method: "DELETE" }));
    expect(screen.getByRole("button", { name: "☆ Save" })).toHaveAttribute("aria-pressed", "false");
  });
});
