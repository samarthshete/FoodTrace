import { describe, expect, it } from "vitest";

import { safeNext } from "./next-path";

describe("[ACC-19] where to go after signing in", () => {
  it("keeps paths on this site, and otherwise goes to the account page", () => {
    expect(safeNext("/p/0038000138416")).toBe("/p/0038000138416");
    expect(safeNext(null)).toBe("/account");
    expect(safeNext("https://evil.example")).toBe("/account");
    expect(safeNext("//evil.example")).toBe("/account");
    expect(safeNext("/\\evil.example")).toBe("/account");
  });
});
