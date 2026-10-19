import { describe, expect, it } from "vitest";

import { createReadFilter, InvalidGTIN, normalize, tryNormalize } from "./gtin";

// Same examples as specs/001-gtin.md, so the browser port can't drift from the server.
describe("[SCAN-4] browser GTIN port matches spec 001", () => {
  it.each([
    ["036000291452", "0036000291452"],
    ["0036000291452", "0036000291452"],
    ["96385074", "0000096385074"],
    ["00036000291452", "0036000291452"],
    ["0 36000 29145 2", "0036000291452"],
    ["0-36000-29145-2", "0036000291452"],
    ["4006381333931", "4006381333931"],
  ])("normalizes %s", (raw, expected) => {
    expect(normalize(raw)).toBe(expected);
  });

  it.each([
    ["036000291453", "check digit"],
    ["10036000291459", "case or pallet"],
    ["12345", "digits"],
    ["03600029145A", "only contain digits"],
  ])("rejects %s", (raw, reason) => {
    expect(() => normalize(raw)).toThrow(InvalidGTIN);
    expect(() => normalize(raw)).toThrow(reason);
  });

  it("returns null instead of throwing in tryNormalize", () => {
    expect(tryNormalize("nope")).toBeNull();
  });
});

describe("[SCAN-5] read filter needs the same valid code twice in a row", () => {
  it("accepts on the second identical read", () => {
    const accept = createReadFilter();
    expect(accept("036000291452")).toBeNull();
    expect(accept("036000291452")).toBe("0036000291452");
  });

  it("resets when a different valid code is read", () => {
    const accept = createReadFilter();
    accept("036000291452");
    expect(accept("4006381333931")).toBeNull();
    expect(accept("036000291452")).toBeNull();
  });

  it("ignores misreads between two good reads", () => {
    const accept = createReadFilter();
    accept("036000291452");
    expect(accept("036000291453")).toBeNull(); // bad check digit
    expect(accept("036000291452")).toBe("0036000291452");
  });

  it("treats UPC-A and its EAN-13 form as the same code", () => {
    const accept = createReadFilter();
    accept("036000291452");
    expect(accept("0036000291452")).toBe("0036000291452");
  });
});
