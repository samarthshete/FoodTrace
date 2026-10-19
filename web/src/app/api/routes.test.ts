import { afterEach, describe, expect, it, vi } from "vitest";

import { GET as contributionConfig } from "./contributions/config/route";
import { POST as contribute } from "./contributions/route";
import { GET as search } from "./search/route";

afterEach(() => vi.unstubAllGlobals());

function stubFetch(impl: (url: string, init?: RequestInit) => Promise<Response>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => impl(String(input), init));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("[SEARCH-7] search route", () => {
  it("proxies to the API with up to 8 suggestions and keeps its status and caching", async () => {
    const fetchMock = stubFetch(async () =>
      Response.json({ results: [] }, { headers: { "Cache-Control": "public, max-age=300" } }),
    );
    const res = await search(new Request("http://web/api/search?q=oat%20milk"));
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/search?q=oat%20milk&limit=8");
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("public, max-age=300");
  });

  it("answers 503 when the API is unreachable", async () => {
    stubFetch(async () => {
      throw new TypeError("fetch failed");
    });
    expect((await search(new Request("http://web/api/search?q=oat"))).status).toBe(503);
  });
});

describe("[CONTRIB-8] contribution route", () => {
  it("forwards the body and the client address, and passes the API's status through", async () => {
    const fetchMock = stubFetch(async () => Response.json({ gtin: "0000000000017" }, { status: 201 }));
    const req = new Request("http://web/api/contributions", {
      method: "POST",
      body: JSON.stringify({ gtin: "0000000000017" }),
      headers: { "x-forwarded-for": "203.0.113.7" },
    });
    const res = await contribute(req);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/contributions");
    expect((init!.headers as Record<string, string>)["X-Forwarded-For"]).toBe("203.0.113.7");
    expect(init!.body).toBe('{"gtin":"0000000000017"}');
    expect(res.status).toBe(201);
  });

  it("answers 503 when the API is unreachable", async () => {
    stubFetch(async () => {
      throw new TypeError("fetch failed");
    });
    const req = new Request("http://web/api/contributions", { method: "POST", body: "{}" });
    expect((await contribute(req)).status).toBe(503);
  });
});

describe("[CONTRIB-9] sharing config route", () => {
  it("passes the API's answer through and defaults to not sharing", async () => {
    stubFetch(async () => Response.json({ can_share_with_off: true }));
    expect(await (await contributionConfig()).json()).toEqual({ can_share_with_off: true });
    stubFetch(async () => new Response(null, { status: 500 }));
    expect(await (await contributionConfig()).json()).toEqual({ can_share_with_off: false });
    stubFetch(async () => {
      throw new TypeError("fetch failed");
    });
    expect(await (await contributionConfig()).json()).toEqual({ can_share_with_off: false });
  });
});
