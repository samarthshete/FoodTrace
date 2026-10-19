import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AssistantProduct, Parsed } from "@/lib/assistant";
import type { SearchOutcome } from "@/lib/search";

import { Assistant } from "./Assistant";

const PRINGLES: AssistantProduct = {
  gtin: "0038000138416", name: "Original", brand: "Pringles",
  nutrition: { sugars_g: { value: 1.5 }, salt_g: { value: 1.3 } },
  allergens: ["en:milk"], allergens_known: true, additives: [],
  score: { status: "scored", total: 49, band: { label: "Mediocre" }, nutriscore: { class: "general", grade: "d" } },
};
const found = vi.fn(async (): Promise<SearchOutcome> => ({ kind: "ok", gtin: null,
  results: [{ gtin: PRINGLES.gtin, name: "Original", brand: "Pringles", image_url: null, total: 49, band: null }] }));
const product = vi.fn(async () => PRINGLES);
const speech = { speak: vi.fn(), cancel: vi.fn() };
class Utterance { lang = ""; onend: (() => void) | null = null; onerror: (() => void) | null = null; constructor(public text: string) {} }
class FakeRecognition {
  static instances: FakeRecognition[] = [];
  lang = ""; interimResults = true; start = vi.fn(); stop = vi.fn();
  onresult: ((e: unknown) => void) | null = null; onerror: (() => void) | null = null; onend: (() => void) | null = null;
  constructor() { FakeRecognition.instances.push(this); }
}

beforeEach(() => {
  found.mockClear(); product.mockClear(); speech.speak.mockReset(); localStorage.clear();
  vi.stubGlobal("speechSynthesis", speech);
  vi.stubGlobal("SpeechSynthesisUtterance", Utterance);
});
afterEach(() => vi.unstubAllGlobals());

async function ask(q: string) {
  fireEvent.change(screen.getByLabelText("Your question"), { target: { value: q } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled());
}
const conversation = () => screen.getByRole("list", { name: "Conversation" });

describe("[ASSIST-4] finds the product and answers", () => {
  it("searches the product words, fetches the product, answers and links to it", async () => {
    render(<Assistant search={found} fetchProduct={product} />);
    await ask("Hey, I'm a diabetes person. Can I eat Pringles?");
    expect(found).toHaveBeenCalledWith("pringles");
    expect(product).toHaveBeenCalledWith(PRINGLES.gtin);
    const items = within(conversation()).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("You: Hey, I'm a diabetes person. Can I eat Pringles?");
    expect(items[1]).toHaveTextContent("For blood sugar: Sugars: 1.5 g per 100 g, which is low");
    expect(within(items[1]).getByRole("link", { name: "See the product" })).toHaveAttribute("href", `/p/${PRINGLES.gtin}`);
  });

  it("uses a typed barcode directly", async () => {
    const byBarcode = vi.fn(async (): Promise<SearchOutcome> => ({ kind: "ok", gtin: PRINGLES.gtin, results: [] }));
    render(<Assistant search={byBarcode} fetchProduct={product} />);
    await ask("tell me about 038000138416");
    expect(product).toHaveBeenCalledWith(PRINGLES.gtin);
  });
});

describe("[ASSIST-2] follow-ups and missing products", () => {
  it("reuses the last product, and asks which product when there is none", async () => {
    render(<Assistant search={found} fetchProduct={product} />);
    await ask("what about its salt?");
    expect(conversation()).toHaveTextContent("Which product?");
    await ask("Pringles");
    await ask("and for blood pressure?");
    expect(found).toHaveBeenCalledTimes(1);
    expect(within(conversation()).getAllByRole("listitem").at(-1)).toHaveTextContent("Salt: 1.3 g per 100 g");
  });
});

describe("[ASSIST-8] not found and errors", () => {
  it("says it couldn't find the product, or can't look it up", async () => {
    const none = vi.fn(async (): Promise<SearchOutcome> => ({ kind: "ok", gtin: null, results: [] }));
    const { unmount } = render(<Assistant search={none} fetchProduct={product} />);
    await ask("diabetic, zzqx crackers");
    expect(conversation()).toHaveTextContent('I couldn\'t find "zzqx crackers"');
    unmount();
    const down = vi.fn(async (): Promise<SearchOutcome> => ({ kind: "error" }));
    render(<Assistant search={down} fetchProduct={product} />);
    await ask("Pringles");
    expect(conversation()).toHaveTextContent("I can't look that up right now.");
  });
});

describe("[ASSIST-9] the page: microphone, transcript and typing", () => {
  it("has a pulsing mic while listening and an always-working text box", () => {
    vi.stubGlobal("webkitSpeechRecognition", FakeRecognition);
    localStorage.setItem("foodtrace.voice-consent", "yes");
    const { container } = render(<Assistant search={found} fetchProduct={product} />);
    const mic = screen.getByRole("button", { name: "Ask by voice" });
    expect(mic).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(mic);
    expect(screen.getByRole("button", { name: "Stop listening" })).toHaveAttribute("aria-pressed", "true");
    expect(container.querySelector(".animate-ping")).not.toBeNull();
    expect(screen.getByLabelText("Your question")).toBeEnabled();
  });
});

describe("[ASSIST-10] speech in and out", () => {
  it("asks for consent first, then answers what it heard and speaks it", async () => {
    vi.stubGlobal("webkitSpeechRecognition", FakeRecognition);
    render(<Assistant search={found} fetchProduct={product} />);
    fireEvent.click(screen.getByRole("button", { name: "Ask by voice" }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent("sent to Google");
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    const rec = FakeRecognition.instances.at(-1)!;
    expect(rec.start).toHaveBeenCalled();
    await act(async () => rec.onresult?.({ results: [[{ transcript: "is Pringles vegan" }]] }));
    await waitFor(() => expect(speech.speak).toHaveBeenCalled());
    expect((speech.speak.mock.calls.at(-1)![0] as Utterance).text).toContain("Pringles Original.");
  });

  it("works by typing without speech support", async () => {
    vi.stubGlobal("speechSynthesis", undefined);
    delete (window as unknown as Record<string, unknown>).speechSynthesis;
    render(<Assistant search={found} fetchProduct={product} />);
    expect(screen.queryByRole("button", { name: "Ask by voice" })).toBeNull();
    expect(screen.getByText(/Type your question below/)).toBeInTheDocument();
    await ask("Pringles");
    expect(conversation()).toHaveTextContent("Pringles Original.");
  });
});

describe("[ASSIST-15] [ASSIST-16] understanding with the LLM route", () => {
  const llm = (parsed: object) => vi.fn(async () => ({ conditions: [], topics: [], productQuery: null, ...parsed }));

  it("answers from the route's fields, including other concerns", async () => {
    const understand = llm({ productQuery: "Pringles", concerns: [{ label: "dental issues", nutrients: ["sugars"] }] });
    render(<Assistant search={found} fetchProduct={product} understand={understand} />);
    await ask("I have dental issues, is Pringles ok");
    expect(understand).toHaveBeenCalledWith("I have dental issues, is Pringles ok");
    expect(found).toHaveBeenCalledTimes(1); // the early keyword search is reused (ASSIST-21)
    expect(conversation()).toHaveTextContent("For dental issues: Sugars: 1.5 g per 100 g, which is low");
  });

  it("asks which one for a broad product instead of picking", async () => {
    const many = vi.fn(async (): Promise<SearchOutcome> => ({ kind: "ok", gtin: null, results: [
      { gtin: "1", name: "Milk Chocolate", brand: "Hershey's", image_url: null, total: 20, band: null },
      { gtin: "2", name: "Dark", brand: "Lindt", image_url: null, total: 30, band: null },
    ] }));
    render(<Assistant search={many} fetchProduct={product} understand={llm({ productQuery: "chocolate", generic: true })} />);
    await ask("is chocolate ok for my teeth");
    expect(conversation()).toHaveTextContent("Which chocolate do you mean? For example: Hershey's Milk Chocolate or Lindt Dark.");
    expect(product).not.toHaveBeenCalled();
  });

  it("falls back to the keyword rules when the route fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 503 })));
    render(<Assistant search={found} fetchProduct={product} />);
    await ask("I'm diabetic, can I eat Pringles?");
    expect(found).toHaveBeenCalledWith("pringles");
    expect(conversation()).toHaveTextContent("For blood sugar:");
  });

  it("says where questions are sent", () => {
    render(<Assistant search={found} fetchProduct={product} />);
    expect(screen.getByText(/Questions are sent to Groq/)).toBeInTheDocument();
  });
});

describe("[ASSIST-19] [ASSIST-20] Whisper speech to text", () => {
  const llm = vi.fn(async (q: string) => ({ conditions: [], topics: [], productQuery: q.includes("Pringles") ? "Pringles" : null }));
  function whisperVoice(text: string | null, startFails = false) {
    const stop = vi.fn(async () => new Blob(["a"], { type: "audio/webm" }));
    return {
      stop,
      voice: {
        enabled: vi.fn(async () => true),
        canRecord: () => true,
        start: vi.fn(async () => {
          if (startFails) throw new Error("denied");
          return { stop };
        }),
        transcribe: vi.fn(async () => text),
      },
    };
  }
  const mic = () => screen.findByRole("button", { name: "Ask by voice" });

  it("records after its own Groq notice, then transcribes and answers", async () => {
    localStorage.setItem("foodtrace.voice-consent", "yes"); // the Google notice doesn't count for Groq
    const { voice, stop } = whisperVoice("I'm diabetic, can I eat Pringles?");
    render(<Assistant search={found} fetchProduct={product} understand={llm} voice={voice} />);
    await waitFor(() => expect(screen.getByText("Tap and ask")).toBeInTheDocument());
    fireEvent.click(await mic());
    expect(screen.getByRole("alertdialog")).toHaveTextContent("sent to Groq");
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(voice.start).toHaveBeenCalled());
    expect(localStorage.getItem("foodtrace.voice-consent-groq")).toBe("yes");
    const stopButton = await screen.findByRole("button", { name: "Stop listening" });
    expect(screen.getByText("Listening… tap again when you're done")).toBeInTheDocument();
    fireEvent.click(stopButton);
    await waitFor(() => expect(conversation()).toHaveTextContent("Pringles Original."));
    expect(stop).toHaveBeenCalled();
    expect(voice.transcribe).toHaveBeenCalled();
    expect(conversation()).toHaveTextContent("You: I'm diabetic, can I eat Pringles?");
  });

  it("stops on its own after 12 seconds", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    localStorage.setItem("foodtrace.voice-consent-groq", "yes");
    const { voice, stop } = whisperVoice("Pringles");
    render(<Assistant search={found} fetchProduct={product} understand={llm} voice={voice} />);
    fireEvent.click(await mic());
    await screen.findByRole("button", { name: "Stop listening" });
    await act(async () => vi.advanceTimersByTime(12_000));
    await waitFor(() => expect(stop).toHaveBeenCalled());
    vi.useRealTimers();
  });

  it("says it couldn't make it out when transcription fails", async () => {
    localStorage.setItem("foodtrace.voice-consent-groq", "yes");
    const { voice } = whisperVoice(null);
    render(<Assistant search={found} fetchProduct={product} understand={llm} voice={voice} />);
    fireEvent.click(await mic());
    fireEvent.click(await screen.findByRole("button", { name: "Stop listening" }));
    await waitFor(() => expect(conversation()).toHaveTextContent("I couldn't make that out."));
    expect(found).not.toHaveBeenCalled();
  });

  it("falls back to the browser's recognition when the mic can't record", async () => {
    vi.stubGlobal("webkitSpeechRecognition", FakeRecognition);
    localStorage.setItem("foodtrace.voice-consent-groq", "yes");
    const { voice } = whisperVoice("x", true);
    render(<Assistant search={found} fetchProduct={product} understand={llm} voice={voice} />);
    await waitFor(() => expect(voice.enabled).toHaveBeenCalled());
    const before = FakeRecognition.instances.length;
    fireEvent.click(await mic());
    await waitFor(() => expect(FakeRecognition.instances.length).toBe(before + 1));
    expect(FakeRecognition.instances.at(-1)!.start).toHaveBeenCalled();
  });

  it("says to type when there's no way to record at all", async () => {
    localStorage.setItem("foodtrace.voice-consent-groq", "yes");
    const { voice } = whisperVoice("x", true);
    render(<Assistant search={found} fetchProduct={product} understand={llm} voice={voice} />);
    fireEvent.click(await mic());
    await waitFor(() => expect(conversation()).toHaveTextContent("Type your question instead."));
  });

  it("keeps the browser path when the server has no key", async () => {
    vi.stubGlobal("webkitSpeechRecognition", FakeRecognition);
    localStorage.setItem("foodtrace.voice-consent", "yes");
    const { voice } = whisperVoice("x");
    voice.enabled = vi.fn(async () => false);
    render(<Assistant search={found} fetchProduct={product} understand={llm} voice={voice} />);
    await waitFor(() => expect(voice.enabled).toHaveBeenCalled());
    fireEvent.click(await mic());
    expect(voice.start).not.toHaveBeenCalled();
    expect(FakeRecognition.instances.at(-1)!.start).toHaveBeenCalled();
  });
});

describe("[ASSIST-21] speed and robustness", () => {
  it("searches while the model thinks, and reuses that search when they agree", async () => {
    let release!: () => void;
    const slow = vi.fn(() => new Promise<Parsed>((r) => { release = () => r({ conditions: ["diabetes"], topics: [], productQuery: "Pringles" }); }));
    render(<Assistant search={found} fetchProduct={product} understand={slow} />);
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "diabetic, Pringles?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(found).toHaveBeenCalledWith("pringles")); // before the model answers
    await act(async () => release());
    await waitFor(() => expect(conversation()).toHaveTextContent("For blood sugar:"));
    expect(found).toHaveBeenCalledTimes(1);
  });

  it("uses the keyword product when the model names none", async () => {
    const none = vi.fn(async (): Promise<Parsed> => ({ conditions: ["teeth"], topics: [], productQuery: null }));
    render(<Assistant search={found} fetchProduct={product} understand={none} />);
    await ask("I have a dental problem, which Pringles brand should I eat?");
    expect(found).toHaveBeenCalledWith("pringles");
    expect(conversation()).toHaveTextContent("For teeth: Sugars: 1.5 g per 100 g");
  });

  it("searches the model's product when it differs from the keywords", async () => {
    const other = vi.fn(async (): Promise<Parsed> => ({ conditions: [], topics: [], productQuery: "Pringles Original" }));
    render(<Assistant search={found} fetchProduct={product} understand={other} />);
    await ask("tell me about those pringles chips");
    expect(found).toHaveBeenCalledWith("Pringles Original");
  });
});
