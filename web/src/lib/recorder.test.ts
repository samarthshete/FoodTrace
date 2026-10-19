import { afterEach, describe, expect, it, vi } from "vitest";

import { canRecord, startRecording, transcribe, whisperEnabled } from "./recorder";

afterEach(() => vi.unstubAllGlobals());

class FakeMediaRecorder {
  static isTypeSupported = (t: string) => t === "audio/webm";
  state = "inactive";
  mimeType: string;
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: ((e: Event) => void) | null = null;
  constructor(_stream: unknown, opts?: { mimeType?: string }) { this.mimeType = opts?.mimeType ?? ""; }
  start() { this.state = "recording"; }
  stop() { this.state = "inactive"; this.ondataavailable?.({ data: new Blob(["abc"]) }); this.onstop?.(new Event("stop")); }
}

describe("[ASSIST-19] recording a clip", () => {
  it("knows when the browser can record", () => {
    expect(canRecord()).toBe(false); // jsdom has neither
    vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
    vi.stubGlobal("navigator", { mediaDevices: { getUserMedia: vi.fn() } });
    expect(canRecord()).toBe(true);
  });

  it("records the mic, then stops it and returns the clip", async () => {
    const track = { stop: vi.fn() };
    vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
    vi.stubGlobal("navigator", { mediaDevices: { getUserMedia: vi.fn(async () => ({ getTracks: () => [track] })) } });
    const rec = await startRecording();
    const blob = await rec.stop();
    expect(blob.type).toBe("audio/webm");
    expect(blob.size).toBe(3);
    expect(track.stop).toHaveBeenCalled(); // the mic light goes off
  });
});

describe("[ASSIST-18] [ASSIST-20] talking to the route", () => {
  it("returns the text, or null on any failure", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ text: " hello " })));
    expect(await transcribe(new Blob(["a"]))).toBe("hello");
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 503 })));
    expect(await transcribe(new Blob(["a"]))).toBeNull();
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("down"); }));
    expect(await transcribe(new Blob(["a"]))).toBeNull();
  });

  it("checks whether Whisper is on", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ enabled: true })));
    expect(await whisperEnabled()).toBe(true);
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ enabled: false })));
    expect(await whisperEnabled()).toBe(false);
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("down"); }));
    expect(await whisperEnabled()).toBe(false);
  });
});
