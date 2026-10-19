import { afterEach, describe, expect, it, vi } from "vitest";

const getToken = vi.hoisted(() => vi.fn());
vi.mock("./auth", () => ({ auth: { api: { getToken } } }));
vi.mock("next/headers", () => ({ headers: async () => new Headers({ cookie: "s=1" }) }));

import { apiToken, fetchAsUser } from "./session";

afterEach(() => vi.unstubAllGlobals());

describe("[ACC-3] the user's API token on the server", () => {
  it("returns the token for a session and null without one", async () => {
    getToken.mockResolvedValueOnce({ token: "jwt-1" });
    expect(await apiToken()).toBe("jwt-1");
    getToken.mockRejectedValueOnce(new Error("no session"));
    expect(await apiToken(new Headers())).toBeNull();
  });

  it("calls the API with the bearer token", async () => {
    const fetchMock = vi.fn(async () => Response.json({}));
    vi.stubGlobal("fetch", fetchMock);
    await fetchAsUser("/me", "jwt-1", { method: "DELETE" });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/me");
    expect(init.method).toBe("DELETE");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer jwt-1");
  });
});
