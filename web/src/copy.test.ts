import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import manifest from "./app/manifest";

const SRC = join(import.meta.dirname);
const BANNED = /\b(toxic|dangerous|unsafe)\b/i;

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "test" ? [] : sourceFiles(path);
    return /\.(tsx?|json)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : [];
  });
}

describe("[PAGE-13] health language", () => {
  it("no user-facing source file uses banned words", () => {
    const offenders = sourceFiles(SRC).filter((f) => BANNED.test(readFileSync(f, "utf8")));
    expect(offenders).toEqual([]);
  });
});

describe("[PWA-1] web app manifest", () => {
  it("is installable: name, start_url, standalone, theme and 192/512 icons", () => {
    const m = manifest();
    expect(m.name).toBe("FoodTrace");
    expect(m.short_name).toBe("FoodTrace");
    expect(m.description).toBe("AI-Powered Grocery Intelligence Platform");
    expect(m.start_url).toBe("/");
    expect(m.display).toBe("standalone");
    expect(m.theme_color).toMatch(/^#/);
    const sizes = (m.icons ?? []).map((i) => i.sizes);
    expect(sizes).toContain("192x192");
    expect(sizes).toContain("512x512");
  });
});
