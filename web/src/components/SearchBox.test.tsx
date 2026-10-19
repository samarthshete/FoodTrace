import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SearchOutcome, SearchResult } from "@/lib/search";
import { searchProducts } from "@/lib/search";

import { SearchBox } from "./SearchBox";

const CHEERIOS: SearchResult = {
  gtin: "0016000275287",
  name: "Cheerios",
  brand: "General Mills",
  image_url: null,
  total: 70,
  band: { id: "good", label: "Good" },
};
const HONEY: SearchResult = { ...CHEERIOS, gtin: "0016000275270", name: "Honey Nut Cheerios", total: null, band: null };

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

function setup(search: (q: string) => Promise<SearchOutcome>) {
  const onSelect = vi.fn();
  render(<SearchBox onSelect={onSelect} search={search} />);
  const input = screen.getByRole("combobox", { name: "Search by name or brand" });
  return { onSelect, input };
}

async function type(input: HTMLElement, value: string) {
  fireEvent.change(input, { target: { value } });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(250);
  });
}

const ok = (results: SearchResult[], gtin: string | null = null) =>
  vi.fn(async () => ({ kind: "ok", results, gtin }) as SearchOutcome);

describe("[SEARCH-7] suggestions as you type", () => {
  it("waits for 2 characters and a 250 ms pause, then lists name, brand and score", async () => {
    const search = ok([CHEERIOS, HONEY]);
    const { input } = setup(search);
    await type(input, "c");
    expect(search).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: "ch" } });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });
    expect(search).not.toHaveBeenCalled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    expect(search).toHaveBeenCalledWith("ch");
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveTextContent("Cheerios");
    expect(options[0]).toHaveTextContent("General Mills");
    expect(options[0]).toHaveTextContent("70 out of 100, Good");
    expect(options[1]).not.toHaveTextContent("out of 100");
  });

  it("calls the web app's own search route", async () => {
    const fetcher = vi.fn(async () => Response.json({ results: [CHEERIOS], gtin: null }));
    const outcome = await searchProducts("oat milk", fetcher);
    expect(fetcher).toHaveBeenCalledWith("/api/search?q=oat%20milk");
    expect(outcome).toEqual({ kind: "ok", results: [CHEERIOS], gtin: null });
  });
});

describe("[SEARCH-8] combobox keyboard behaviour", () => {
  it("moves with arrows, opens with Enter, closes with Escape, and announces the count", async () => {
    const { input, onSelect } = setup(ok([CHEERIOS, HONEY]));
    await type(input, "cheerios");
    expect(screen.getByRole("status")).toHaveTextContent("2 products found.");
    expect(input).toHaveAttribute("aria-expanded", "true");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getAllByRole("option")[1]).toHaveAttribute("aria-selected", "true");
    expect(input.getAttribute("aria-activedescendant")).toBe(screen.getAllByRole("option")[1].id);
    fireEvent.keyDown(input, { key: "ArrowUp" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith(CHEERIOS.gtin);
    fireEvent.keyDown(input, { key: "Escape" });
    expect(input).toHaveAttribute("aria-expanded", "false");
  });

  it("opens a product when its suggestion is clicked", async () => {
    const { input, onSelect } = setup(ok([CHEERIOS]));
    await type(input, "cheerios");
    fireEvent.mouseDown(screen.getByRole("option"));
    expect(onSelect).toHaveBeenCalledWith(CHEERIOS.gtin);
  });
});

describe("[SEARCH-9] barcodes, no results and errors", () => {
  it("opens a typed barcode on Enter", async () => {
    const { input, onSelect } = setup(ok([], "0036000291452"));
    await type(input, "036000291452");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith("0036000291452");
  });

  it("says when nothing matches or search is down", async () => {
    const { input } = setup(ok([]));
    await type(input, "zzzz");
    expect(screen.getByRole("status")).toHaveTextContent("No products match.");

    const failing = vi.fn(async () => ({ kind: "error" }) as SearchOutcome);
    const other = render(<SearchBox onSelect={vi.fn()} search={failing} />);
    await type(other.getAllByRole("combobox")[1], "oats");
    expect(other.getAllByRole("status")[1]).toHaveTextContent("Search isn't available right now.");
  });

  it("maps a failed request to an error, not a crash", async () => {
    expect(await searchProducts("x", vi.fn(async () => new Response(null, { status: 503 })))).toEqual({ kind: "error" });
    expect(await searchProducts("x", vi.fn().mockRejectedValue(new TypeError("offline")))).toEqual({ kind: "error" });
  });
});

describe("[SEARCH-10] only the latest query wins", () => {
  it("ignores a slow response to an earlier query", async () => {
    let releaseFirst: (o: SearchOutcome) => void = () => {};
    const search = vi
      .fn()
      .mockImplementationOnce(() => new Promise<SearchOutcome>((r) => (releaseFirst = r)))
      .mockImplementationOnce(async () => ({ kind: "ok", results: [HONEY], gtin: null }));
    const { input } = setup(search);
    await type(input, "che");
    await type(input, "honey");
    await act(async () => {
      releaseFirst({ kind: "ok", results: [CHEERIOS], gtin: null });
      await vi.advanceTimersByTimeAsync(0);
    });
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(1);
    expect(options[0]).toHaveTextContent("Honey Nut Cheerios");
  });
});
