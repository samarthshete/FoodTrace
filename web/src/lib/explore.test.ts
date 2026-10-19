import { afterEach, describe, expect, it, vi } from "vitest";

import { CATEGORIES, loadCategory, loadExplore } from "./explore";

afterEach(() => vi.unstubAllGlobals());

describe("[EXPLORE-6] loading top foods", () => {
  it("asks the API for the top products per category", async () => {
    const fetchMock = vi.fn(async () => Response.json({ categories: [{ id: "breakfast", products: [] }] }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await loadExplore(4)).toEqual([{ id: "breakfast", products: [] }]);
    expect((fetchMock.mock.calls[0] as unknown as [string])[0]).toBe("http://localhost:8000/explore?per_category=4");
  });

  it("loads one category", async () => {
    const fetchMock = vi.fn(async () => Response.json({ id: "cheese", products: [] }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await loadCategory("cheese")).toEqual({ id: "cheese", products: [] });
    expect((fetchMock.mock.calls[0] as unknown as [string])[0]).toBe("http://localhost:8000/explore/cheese?limit=48");
  });

  it("returns null when the API fails or is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 404 })));
    expect(await loadCategory("nope")).toBeNull();
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("down"); }));
    expect(await loadExplore()).toBeNull();
  });

  it("knows the same ten categories as the API", () => {
    expect(CATEGORIES.map((c) => c.id)).toEqual([
      "breakfast", "yogurts", "breads", "snacks", "bars", "sweets", "drinks", "cheese", "meals", "spreads",
    ]);
  });
});
