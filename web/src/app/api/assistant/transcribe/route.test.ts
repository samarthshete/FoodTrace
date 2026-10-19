// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET, POST } from "./route";

let n = 0;
function send(audio: Blob | string | null, ip = `10.1.0.${++n}`) {
  const form = new FormData();
  if (audio !== null) form.set("audio", audio);
  return POST(new Request("http://web/api/assistant/transcribe", { method: "POST", body: form, headers: { "x-forwarded-for": ip } }));
}
const clip = (type = "audio/webm", size = 10) => new Blob([new Uint8Array(size)], { type });
const groq = (body: unknown, status = 200) => vi.fn(async () => Response.json(body, { status }));

beforeEach(() => vi.stubEnv("GROQ_API_KEY", "test-key"));
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

describe("[ASSIST-18] the transcribe route", () => {
  it("sends only the clip to Groq Whisper and returns the text", async () => {
    const fetchMock = groq({ text: " I'm diabetic, can I eat Pringles? " });
    vi.stubGlobal("fetch", fetchMock);
    const res = await send(clip("audio/mp4"));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ text: "I'm diabetic, can I eat Pringles?" });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://api.groq.com/openai/v1/audio/transcriptions");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-key");
    const form = init.body as FormData;
    expect(form.get("model")).toBe("whisper-large-v3-turbo");
    expect(form.get("language")).toBe("en");
    expect((form.get("file") as File).name).toBe("question.m4a");
    expect([...form.keys()].sort()).toEqual(["file", "language", "model", "prompt", "response_format", "temperature"]);
  });

  it("names other formats by type", async () => {
    for (const [type, ext] of [["audio/ogg", "ogg"], ["audio/wav", "wav"], ["audio/mpeg", "mp3"], ["", "webm"]]) {
      const fetchMock = groq({ text: "hi" });
      vi.stubGlobal("fetch", fetchMock);
      await send(clip(type));
      const form = (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body as FormData;
      expect((form.get("file") as File).name).toBe(`question.${ext}`);
    }
  });

  it("says whether it's enabled, and is 404 without a key", async () => {
    expect(await GET().json()).toEqual({ enabled: true });
    vi.stubEnv("GROQ_API_KEY", "");
    expect(await GET().json()).toEqual({ enabled: false });
    expect((await send(clip())).status).toBe(404);
  });

  it("rejects a missing, empty or too-large clip", async () => {
    expect((await send(null)).status).toBe(400);
    expect((await send("text")).status).toBe(400);
    expect((await send(clip("audio/webm", 0))).status).toBe(400);
    expect((await send(clip("audio/webm", 4 * 1024 * 1024 + 1))).status).toBe(413);
  });

  it("is 503 when Groq fails or hears nothing", async () => {
    vi.stubGlobal("fetch", groq({}, 500));
    expect((await send(clip())).status).toBe(503);
    vi.stubGlobal("fetch", groq({ text: "   " }));
    expect((await send(clip())).status).toBe(503);
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("timeout"); }));
    expect((await send(clip())).status).toBe(503);
  });

  it("allows 20 clips a minute per client", async () => {
    vi.stubGlobal("fetch", groq({ text: "hi" }));
    const codes = [];
    for (let i = 0; i < 21; i++) codes.push((await send(clip(), "192.168.9.9")).status);
    expect(codes.slice(0, 20).every((c) => c === 200)).toBe(true);
    expect(codes[20]).toBe(429);
  });
});
