import { afterEach, describe, expect, it, vi } from "vitest";

import { GET } from "./route";

afterEach(() => vi.unstubAllGlobals());
const params = (gtin: string) => ({ params: Promise.resolve({ gtin }) });

describe("[ASSIST-4] product proxy", () => {
  it("passes the API's product and status through", async () => {
    const fetchMock = vi.fn(async () => Response.json({ gtin: "0038000138416" }, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await GET(new Request("http://web/api/products/0038000138416"), params("0038000138416"));
    expect((fetchMock.mock.calls[0] as unknown as [string])[0]).toBe("http://localhost:8000/products/0038000138416");
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ gtin: "0038000138416" });
  });

  it("answers 503 when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("down"); }));
    expect((await GET(new Request("http://web/api/products/1"), params("1"))).status).toBe(503);
  });
});
