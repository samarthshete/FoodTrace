import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

let n = 0;
const ask = (question: unknown, ip = `10.0.0.${++n}`) =>
  POST(new Request("http://web/api/assistant/understand", {
    method: "POST", headers: { "Content-Type": "application/json", "x-forwarded-for": ip },
    body: JSON.stringify({ question }),
  }));
const groq = (content: string, status = 200) =>
  vi.fn(async () => Response.json({ choices: [{ message: { content } }] }, { status }));

beforeEach(() => vi.stubEnv("GROQ_API_KEY", "test-key"));
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

describe("[ASSIST-12] the understand route", () => {
  it("sends only the question, with the key, and returns checked fields", async () => {
    const fetchMock = groq(JSON.stringify({ product: "Pringles", conditions: ["diabetes"], topics: [] }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await ask("I'm diabetic, can I eat Pringles?");
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ productQuery: "Pringles", conditions: ["diabetes"] });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://api.groq.com/openai/v1/chat/completions");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-key");
    const body = JSON.parse(init.body as string);
    expect(body).toMatchObject({ model: "openai/gpt-oss-20b", temperature: 0 });
    expect(body.messages[1]).toEqual({ role: "user", content: "I'm diabetic, can I eat Pringles?" });
  });

  it("is 404 without a key and 400 for empty or long questions", async () => {
    expect((await ask("x".repeat(301))).status).toBe(400);
    expect((await ask("  ")).status).toBe(400);
    expect((await ask(42)).status).toBe(400);
    vi.stubEnv("GROQ_API_KEY", "");
    expect((await ask("Pringles")).status).toBe(404);
  });

  it("is 503 when Groq fails or returns unusable output", async () => {
    vi.stubGlobal("fetch", groq("{}", 500));
    expect((await ask("Pringles")).status).toBe(503);
    vi.stubGlobal("fetch", groq("not json"));
    expect((await ask("Pringles")).status).toBe(503);
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("timeout"); }));
    expect((await ask("Pringles")).status).toBe(503);
  });

  it("allows 20 questions a minute per client", async () => {
    vi.stubGlobal("fetch", groq(JSON.stringify({ product: "x" })));
    const codes = [];
    for (let i = 0; i < 21; i++) codes.push((await ask("Pringles", "192.168.1.1")).status);
    expect(codes.slice(0, 20).every((c) => c === 200)).toBe(true);
    expect(codes[20]).toBe(429);
  });
});
