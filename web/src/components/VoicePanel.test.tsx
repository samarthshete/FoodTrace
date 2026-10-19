import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Breakdown, Product } from "@/lib/api";
import scored from "@/test/fixtures/scored.json";

import { VoicePanel } from "./VoicePanel";

const { product, breakdown } = scored as unknown as { product: Product; breakdown: Breakdown };
const data = { product, breakdown, alternatives: null };

class Utterance {
  lang = "";
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public text: string) {}
}
const speech = { speak: vi.fn(), cancel: vi.fn() };

class FakeRecognition {
  static instances: FakeRecognition[] = [];
  start = vi.fn();
  onresult: ((e: unknown) => void) | null = null;
  onend: (() => void) | null = null;
  constructor() {
    FakeRecognition.instances.push(this);
  }
}

beforeEach(() => {
  speech.speak.mockReset();
  vi.stubGlobal("speechSynthesis", speech);
  vi.stubGlobal("SpeechSynthesisUtterance", Utterance);
  localStorage.clear();
});
afterEach(() => vi.unstubAllGlobals());

describe("[VOICE-5] read aloud", () => {
  it("speaks the summary and toggles to Stop", () => {
    render(<VoicePanel data={data} />);
    fireEvent.click(screen.getByRole("button", { name: "Read aloud" }));
    const said = speech.speak.mock.calls[0][0] as Utterance;
    expect(said.text).toMatch(/scores 49 out of 100/);
    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
    act(() => said.onend?.());
    expect(screen.getByRole("button", { name: "Read aloud" })).toBeInTheDocument();
  });

  it("is hidden without speech support", () => {
    vi.stubGlobal("speechSynthesis", undefined);
    // `in window` still sees the stubbed key, so remove it entirely.
    delete (window as unknown as Record<string, unknown>).speechSynthesis;
    render(<VoicePanel data={data} />);
    expect(screen.queryByRole("button", { name: "Read aloud" })).toBeNull();
  });
});

describe("[VOICE-6] typed questions", () => {
  it("shows the answer in a live region and speaks it", () => {
    render(<VoicePanel data={data} />);
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "what's the score?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(screen.getByText(/scores 49 out of 100/)).toHaveAttribute("aria-live", "polite");
    expect((speech.speak.mock.calls[0][0] as Utterance).text).toMatch(/scores 49/);
  });
});

describe("[VOICE-7] voice input needs a tap and a one-time notice", () => {
  it("asks first, then listens and answers what it heard", () => {
    vi.stubGlobal("webkitSpeechRecognition", FakeRecognition);
    render(<VoicePanel data={data} />);
    fireEvent.click(screen.getByRole("button", { name: /Ask by voice/ }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent("sent to Google");
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    const recognizer = FakeRecognition.instances.at(-1)!;
    expect(recognizer.start).toHaveBeenCalled();
    expect(localStorage.getItem("foodtrace.voice-consent")).toBe("yes");
    act(() => recognizer.onresult?.({ results: [[{ transcript: "any additives" }]] }));
    expect(screen.getByText(/E250 - Sodium nitrite/)).toBeInTheDocument();
  });

  it("has no microphone button without speech recognition", () => {
    render(<VoicePanel data={data} />);
    expect(screen.queryByRole("button", { name: /Ask by voice/ })).toBeNull();
    expect(screen.getByRole("button", { name: "Ask" })).toBeInTheDocument();
  });
});

describe("[VOICE-8] speech errors don't break the page", () => {
  it("still shows the typed answer when speaking throws", () => {
    speech.speak.mockImplementation(() => {
      throw new Error("not allowed");
    });
    render(<VoicePanel data={data} />);
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "score" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(screen.getByText(/scores 49 out of 100/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Read aloud" })).toBeInTheDocument();
  });
});
