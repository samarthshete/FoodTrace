import { afterEach, describe, expect, it, vi } from "vitest";

const token = vi.hoisted(() => ({ value: null as string | null }));
vi.mock("@/lib/session", async () => {
  const actual = await vi.importActual<typeof import("@/lib/session")>("@/lib/session");
  return { ...actual, apiToken: async () => token.value };
});

import { DELETE, GET, PUT } from "./[[...path]]/route";

afterEach(() => vi.unstubAllGlobals());
const params = (path?: string[]) => ({ params: Promise.resolve({ path }) });

describe("[ACC-3] the /api/me proxy", () => {
  it("is 401 without a session and never calls the API", async () => {
    token.value = null;
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect((await GET(new Request("http://web/api/me"), params())).status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("forwards to /me with the user's bearer token", async () => {
    token.value = "jwt-123";
    const fetchMock = vi.fn(async () => Response.json({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await GET(new Request("http://web/api/me/history?cursor=7"), params(["history"]));
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/me/history?cursor=7");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer jwt-123");
    await GET(new Request("http://web/api/me"), params());
    expect((fetchMock.mock.calls[1] as unknown as [string])[0]).toBe("http://localhost:8000/me");
  });

  it("passes bodies and 204s through", async () => {
    token.value = "jwt-123";
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const put = new Request("http://web/api/me/preferences", { method: "PUT", body: '{"diets":[]}' });
    expect((await PUT(put, params(["preferences"]))).status).toBe(204);
    expect((fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body).toBe('{"diets":[]}');
    expect((await DELETE(new Request("http://web/api/me", { method: "DELETE" }), params())).status).toBe(204);
  });
});
