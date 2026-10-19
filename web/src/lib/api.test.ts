import { describe, expect, it, vi } from "vitest";

import { loadAlternatives, loadProduct, loadRecalls } from "./api";

function respond(status: number, body: unknown = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("[PAGE-11] API states map to page states", () => {
  it("loads the product, then the breakdown, in that order", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(respond(200, { gtin: "0036000291452" }))
      .mockResolvedValueOnce(respond(200, { explanation: [] }));
    const result = await loadProduct("0036000291452", fetcher);
    expect(result.kind).toBe("ok");
    expect(fetcher.mock.calls[0][0]).toMatch(/\/products\/0036000291452$/);
    expect(fetcher.mock.calls[1][0]).toMatch(/\/products\/0036000291452\/breakdown$/);
  });

  it("404 is not_found", async () => {
    const result = await loadProduct("x", vi.fn().mockResolvedValue(respond(404)));
    expect(result).toEqual({ kind: "not_found", gtin: "x" });
  });

  it("422 is invalid with the API's reason", async () => {
    const fetcher = vi.fn().mockResolvedValue(respond(422, { detail: "The check digit doesn't match." }));
    expect(await loadProduct("x", fetcher)).toEqual({
      kind: "invalid",
      detail: "The check digit doesn't match.",
    });
  });

  it.each([503, 500])("%s is unavailable", async (status) => {
    expect((await loadProduct("x", vi.fn().mockResolvedValue(respond(status)))).kind).toBe(
      "unavailable",
    );
  });

  it("a network error is unavailable, not a crash", async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError("fetch failed"));
    expect((await loadProduct("x", fetcher)).kind).toBe("unavailable");
  });
});

describe("[ALT-11] [RECALL-14] page extras never break the product page", () => {
  it.each([
    ["alternatives", loadAlternatives, "/alternatives"],
    ["recalls", loadRecalls, "/recalls"],
  ] as const)("%s: returns the body on success and null on any failure", async (_, load, suffix) => {
    const ok = vi.fn().mockResolvedValue(respond(200, { gtin: "0036000291452" }));
    expect(await load("0036000291452", ok)).toEqual({ gtin: "0036000291452" });
    expect(ok.mock.calls[0][0]).toMatch(new RegExp(`/products/0036000291452${suffix}$`));
    expect(await load("x", vi.fn().mockResolvedValue(respond(503)))).toBeNull();
    expect(await load("x", vi.fn().mockRejectedValue(new TypeError("fetch failed")))).toBeNull();
  });
});
