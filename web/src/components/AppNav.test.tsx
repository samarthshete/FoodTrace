import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/explore/breakfast" }));

import { BottomTabs, BottomTabsView, HeaderTabs, HeaderTabsView } from "./AppNav";
import { CategoryNav, CategoryNavView } from "./CategoryNav";

describe("[EXPLORE-7] app tabs", () => {
  it("has Explore, Scan, Lookup and Assistant in the header and the bottom bar", () => {
    render(
      <>
        <HeaderTabsView path="/scan" />
        <BottomTabsView path="/scan" />
      </>,
    );
    for (const name of ["App", "App tabs"]) {
      const nav = screen.getByRole("navigation", { name });
      const links = within(nav).getAllByRole("link");
      expect(links.map((l) => l.getAttribute("href"))).toEqual(["/explore", "/scan", "/lookup", "/assistant"]);
      expect(within(nav).getByRole("link", { name: "Scan" })).toHaveAttribute("aria-current", "page");
      expect(within(nav).getByRole("link", { name: "Explore" })).not.toHaveAttribute("aria-current");
    }
  });

  it("marks a tab current for its sub-pages, from the URL", () => {
    render(
      <>
        <HeaderTabs />
        <BottomTabs />
      </>,
    );
    for (const name of ["App", "App tabs"]) {
      const nav = screen.getByRole("navigation", { name });
      expect(within(nav).getByRole("link", { name: "Explore" })).toHaveAttribute("aria-current", "page");
    }
  });
});

describe("[EXPLORE-6] categories", () => {
  it("lists top foods and the ten categories, marking the current one", () => {
    render(<CategoryNav />);
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(11);
    expect(links[0]).toHaveAttribute("href", "/explore");
    expect(screen.getByRole("link", { name: /Breakfast cereals/ })).toHaveAttribute("aria-current", "page");
  });

  it("marks Top foods on /explore", () => {
    render(<CategoryNavView path="/explore" />);
    expect(screen.getByRole("link", { name: /Top foods/ })).toHaveAttribute("aria-current", "page");
  });
});
