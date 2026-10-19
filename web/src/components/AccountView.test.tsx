import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { type AccountData, AccountView, groupByDay } from "./AccountView";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh: vi.fn() }) }));
const signOut = vi.fn(async () => {});
vi.mock("@/lib/auth-client", () => ({ signOut: () => signOut() }));

const DATA: AccountData = {
  me: { name: "Alice", email: "alice@example.com", image: null,
        preferences: { allergens: ["milk"], diets: [], save_history: true } },
  history: [
    { id: 3, gtin: "0000000000017", scanned_at: "2026-10-12T15:00:00Z", name: "Bars", brand: null, total: 49, band: { id: "mediocre", label: "Mediocre" } },
    { id: 2, gtin: "0000000000024", scanned_at: "2026-10-12T09:00:00Z", name: "Oats", brand: null, total: 80, band: null },
    { id: 1, gtin: "0000000000031", scanned_at: "2026-10-11T09:00:00Z", name: "Milk", brand: null, total: null, band: null },
  ],
  favorites: [{ gtin: "0000000000024", name: "Oats", brand: null, total: 80 }],
  contributions: [{ gtin: "0000000000048", name: "Granola", created_at: "2026-10-10T00:00:00Z" }],
};

const ok = () => vi.fn(async () => new Response(null, { status: 204 }));

describe("[ACC-5] preferences", () => {
  it("saves allergens, diets and the history pause", async () => {
    const fetcher = ok();
    render(<AccountView data={DATA} fetcher={fetcher} />);
    fireEvent.click(screen.getByLabelText("Sesame"));
    fireEvent.click(screen.getByLabelText("Pause history"));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    const last = JSON.parse(String((fetcher.mock.calls[1] as unknown as [string, RequestInit])[1].body));
    expect(last).toEqual({ allergens: ["milk", "sesame"], diets: [], save_history: false });
  });
});

describe("[ACC-10] history by day", () => {
  it("groups scans by day, newest first, with the score at the time", () => {
    expect(groupByDay(DATA.history).map(([day, items]) => [day, items.length])).toEqual([
      ["Oct 12, 2026", 2], ["Oct 11, 2026", 1],
    ]);
    render(<AccountView data={DATA} fetcher={ok()} />);
    expect(screen.getByRole("link", { name: "Bars" }).closest("li")).toHaveTextContent("49/100 · Mediocre");
  });
});

describe("[ACC-11] deleting history", () => {
  it("removes one scan or all of them", async () => {
    const fetcher = ok();
    render(<AccountView data={DATA} fetcher={fetcher} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove Bars from history" }));
    await waitFor(() => expect(screen.queryByRole("link", { name: "Bars" })).toBeNull());
    expect(fetcher).toHaveBeenCalledWith("/api/me/history/3", { method: "DELETE" });
    fireEvent.click(screen.getByRole("button", { name: "Delete all history" }));
    await waitFor(() => expect(screen.getByText("No scans saved.")).toBeInTheDocument());
  });
});

describe("[ACC-13] deleting the account", () => {
  it("asks first, then deletes everything and signs out", async () => {
    const fetcher = ok();
    render(<AccountView data={DATA} fetcher={fetcher} />);
    fireEvent.click(screen.getByRole("button", { name: "Delete account" }));
    expect(fetcher).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Yes, delete everything" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    expect(fetcher).toHaveBeenCalledWith("/api/me", { method: "DELETE" });
    expect(signOut).toHaveBeenCalled();
  });
});

describe("[ACC-18] products the user added", () => {
  it("lists contributions on the account page", () => {
    render(<AccountView data={DATA} fetcher={ok()} />);
    const section = screen.getByRole("region", { name: "Products you added" });
    expect(within(section).getByRole("link", { name: "Granola" })).toHaveAttribute("href", "/p/0000000000048");
  });
});
