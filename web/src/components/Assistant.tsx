"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState, useSyncExternalStore } from "react";

import {
  type AssistantProduct,
  NEED_PRODUCT,
  NOT_AVAILABLE,
  type Parsed,
  answerFor,
  clarify,
  notFound,
  parseQuestion,
} from "@/lib/assistant";
import { type Recording, canRecord, startRecording, transcribe, whisperEnabled } from "@/lib/recorder";
import { type SearchOutcome, searchProducts } from "@/lib/search";

import { MicIcon } from "./Icons";

const EXAMPLES = [
  "I'm diabetic. Can I eat Pringles?",
  "Is SPAM Classic ok for high blood pressure?",
  "Peanut allergy: Reese's peanut butter cups?",
];

/** Whisper speech to text (ASSIST-19); injectable for tests. */
export interface VoiceIO {
  enabled: () => Promise<boolean>;
  canRecord: () => boolean;
  start: () => Promise<Recording>;
  transcribe: (clip: Blob) => Promise<string | null>;
}
const WHISPER: VoiceIO = { enabled: whisperEnabled, canRecord, start: startRecording, transcribe };
const MAX_RECORDING_MS = 12_000;
export const COULDNT_HEAR = "I couldn't make that out. Try again, or type your question.";

const CONSENT_KEY = "foodtrace.voice-consent"; // shared with the product page's voice panel (VOICE-7)
const WHISPER_CONSENT_KEY = "foodtrace.voice-consent-groq"; // a new recipient needs its own notice (ASSIST-19)

interface Message {
  id: number;
  role: "you" | "assistant";
  text: string;
  gtin?: string;
}

interface Recognition {
  lang: string;
  interimResults: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}
type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}
function supportSnapshot(): string {
  return [typeof window !== "undefined" && "speechSynthesis" in window ? "speech" : "", recognitionCtor() ? "mic" : ""].join(",");
}
const noSubscribe = () => () => {};

async function fetchProductJson(gtin: string): Promise<AssistantProduct | null> {
  try {
    const res = await fetch(`/api/products/${encodeURIComponent(gtin)}`);
    return res.ok ? ((await res.json()) as AssistantProduct) : null;
  } catch {
    return null;
  }
}

// ASSIST-15: the LLM route first, the keyword rules on any failure.
async function understandQuestion(question: string): Promise<Parsed> {
  try {
    const res = await fetch("/api/assistant/understand", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (res.ok) return (await res.json()) as Parsed;
  } catch {}
  return parseQuestion(question);
}

// The voice assistant tab (spec 023).
export function Assistant({
  search = searchProducts,
  fetchProduct = fetchProductJson,
  understand = understandQuestion,
  voice = WHISPER,
}: {
  search?: (q: string) => Promise<SearchOutcome>;
  fetchProduct?: (gtin: string) => Promise<AssistantProduct | null>;
  understand?: (q: string) => Promise<Parsed>;
  voice?: VoiceIO;
}) {
  const inputId = useId();
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [askConsent, setAskConsent] = useState(false);
  const [whisper, setWhisper] = useState(false);
  const lastGtin = useRef<string | null>(null);
  const recording = useRef<Recording | null>(null);
  const autoStop = useRef<ReturnType<typeof setTimeout> | null>(null);
  const recognition = useRef<Recognition | null>(null);
  const nextId = useRef(0);
  const supported = useSyncExternalStore(noSubscribe, supportSnapshot, () => ",");
  const support = { speech: supported.startsWith("speech"), mic: supported.endsWith("mic") };

  // ASSIST-19: record with Whisper only when the server has a key and the browser can record.
  useEffect(() => {
    let live = true;
    if (voice.canRecord()) {
      void voice.enabled().then((on) => {
        if (live) setWhisper(on);
      });
    }
    return () => {
      live = false;
    };
  }, [voice]);

  useEffect(
    () => () => {
      try {
        window.speechSynthesis?.cancel();
      } catch {}
    },
    [],
  );

  function say(message: Omit<Message, "id">) {
    setMessages((m) => [...m, { ...message, id: nextId.current++ }]);
  }

  function speak(text: string) {
    if (!support.speech) return;
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "en-US";
      u.onend = () => setSpeaking(false);
      u.onerror = () => setSpeaking(false);
      setSpeaking(true);
      window.speechSynthesis.speak(u);
    } catch {
      setSpeaking(false);
    }
  }

  async function ask(raw: string) {
    const q = raw.trim();
    if (!q || busy) return;
    say({ role: "you", text: q });
    setQuestion("");
    setBusy(true);
    try {
      // ASSIST-21: start the keyword search while the LLM is still thinking; reuse it when both
      // agree on the product, and fall back to the keyword guess when the LLM names none.
      const keywords = parseQuestion(q).productQuery;
      const early = keywords ? search(keywords) : null;
      const understood = await understand(q);
      const parsed = understood.productQuery || lastGtin.current ? understood : { ...understood, productQuery: keywords };
      let gtin: string | null = null;
      if (parsed.productQuery) {
        const same = early && parsed.productQuery.toLowerCase() === keywords;
        const outcome = await (same ? early : search(parsed.productQuery)); // ASSIST-4
        if (outcome.kind === "error") return reply(NOT_AVAILABLE);
        const which = parsed.generic && !outcome.gtin ? clarify(parsed.productQuery, outcome.results) : null;
        if (which) return reply(which); // ASSIST-16
        gtin = outcome.gtin ?? outcome.results[0]?.gtin ?? null;
        if (!gtin) return reply(notFound(parsed.productQuery)); // ASSIST-8
      } else {
        gtin = lastGtin.current; // ASSIST-2: follow-up about the last product
        if (!gtin) return reply(NEED_PRODUCT);
      }
      const product = await fetchProduct(gtin);
      if (!product) return reply(NOT_AVAILABLE);
      lastGtin.current = product.gtin;
      reply(answerFor(product, parsed), product.gtin);
    } finally {
      setBusy(false);
    }
  }

  function reply(text: string, gtin?: string) {
    say({ role: "assistant", text, gtin });
    speak(text);
  }

  function listen() {
    let consented = false;
    try {
      consented = localStorage.getItem(whisper ? WHISPER_CONSENT_KEY : CONSENT_KEY) === "yes";
    } catch {}
    if (!consented) return setAskConsent(true); // ASSIST-10, VOICE-7
    if (whisper) return void record();
    listenInBrowser();
  }

  async function record() {
    try {
      recording.current = await voice.start();
    } catch {
      // ASSIST-20: no mic or permission refused: use the browser's recognition if it has one.
      setWhisper(false);
      if (recognitionCtor()) return listenInBrowser();
      return reply("I can't use the microphone here. Type your question instead.");
    }
    setListening(true);
    autoStop.current = setTimeout(() => void finishRecording(), MAX_RECORDING_MS);
  }

  async function finishRecording() {
    if (autoStop.current) clearTimeout(autoStop.current);
    const current = recording.current;
    recording.current = null;
    setListening(false);
    if (!current) return;
    setBusy(true);
    const clip = await current.stop();
    const text = await voice.transcribe(clip);
    setBusy(false);
    if (text) void ask(text);
    else reply(COULDNT_HEAR); // ASSIST-20
  }

  function stopListening() {
    if (recording.current) return void finishRecording();
    recognition.current?.stop();
  }

  function listenInBrowser() {
    const Ctor = recognitionCtor();
    if (!Ctor) return;
    try {
      const r = new Ctor();
      r.lang = "en-US";
      r.interimResults = false;
      r.onresult = (e) => {
        const heard = e.results[0]?.[0]?.transcript ?? "";
        void ask(heard);
      };
      r.onerror = () => setListening(false);
      r.onend = () => setListening(false);
      recognition.current = r;
      setListening(true);
      r.start();
    } catch {
      setListening(false);
    }
  }

  function consent() {
    try {
      localStorage.setItem(whisper ? WHISPER_CONSENT_KEY : CONSENT_KEY, "yes");
    } catch {}
    setAskConsent(false);
    listen();
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col items-center gap-3 py-4">
        {support.mic || whisper ? (
          <button
            type="button"
            onClick={listening ? stopListening : listen}
            aria-pressed={listening}
            aria-label={listening ? "Stop listening" : "Ask by voice"}
            className="relative flex h-28 w-28 items-center justify-center rounded-full bg-gradient-to-b from-emerald-500 to-emerald-700 text-white shadow-[0_10px_30px_-8px_rgba(4,120,87,0.6)] ring-8 ring-emerald-50 transition hover:scale-[1.03] focus-visible:outline focus-visible:outline-4 focus-visible:outline-emerald-300"
          >
            {listening && (
              <span aria-hidden="true" className="absolute inset-0 animate-ping rounded-full bg-emerald-500 opacity-60" />
            )}
            <MicIcon className="relative h-11 w-11" />
          </button>
        ) : (
          <p className="text-sm text-zinc-600">Voice isn&apos;t available in this browser. Type your question below.</p>
        )}
        <p className="text-sm text-zinc-600" aria-live="polite">
          {listening
            ? whisper
              ? "Listening… tap again when you're done"
              : "Listening…"
            : busy
              ? "Looking it up…"
              : support.mic || whisper
                ? "Tap and ask"
                : ""}
        </p>
        {speaking && (
          <button
            type="button"
            onClick={() => {
              window.speechSynthesis.cancel();
              setSpeaking(false);
            }}
            className="btn-secondary px-3 py-1.5"
          >
            Stop speaking
          </button>
        )}
      </div>

      {askConsent && (
        <div role="alertdialog" aria-labelledby="assistant-mic-notice" className="rounded-xl bg-zinc-50 p-4 text-sm ring-1 ring-zinc-200">
          <p id="assistant-mic-notice">
            {whisper
              ? "Voice questions are recorded and sent to Groq, an AI service, to turn them into text. Nothing is stored. You can type instead."
              : "Voice questions use your browser\u2019s speech service. In Chrome, your voice is sent to Google to turn it into text. You can type instead."}
          </p>
          <div className="mt-2 flex gap-3">
            <button type="button" onClick={consent} className="font-medium underline">
              Continue
            </button>
            <button type="button" onClick={() => setAskConsent(false)} className="underline">
              Not now
            </button>
          </div>
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask(question);
        }}
        className="flex gap-2"
      >
        <label htmlFor={inputId} className="sr-only">
          Your question
        </label>
        <input
          id={inputId}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. I have high blood pressure, is Pringles ok?"
          className="field min-w-0 flex-1"
        />
        <button type="submit" disabled={busy} className="btn-primary disabled:opacity-50">
          Ask
        </button>
      </form>
      <p className="-mt-3 text-xs text-zinc-600">
        Questions are sent to Groq, an AI service, only to understand them. Answers come from the product&apos;s label
        data.
      </p>

      {messages.length === 0 && (
        <div className="flex flex-wrap justify-center gap-2">
          {EXAMPLES.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => void ask(q)}
              className="rounded-full bg-zinc-100 px-3.5 py-1.5 text-sm text-zinc-800 hover:bg-zinc-200"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      <ol aria-label="Conversation" aria-live="polite" className="flex flex-col gap-3">
        {messages.map((m) => (
          <li
            key={m.id}
            className={
              m.role === "you"
                ? "max-w-[85%] self-end rounded-2xl rounded-br-md bg-zinc-900 px-4 py-2.5 text-white"
                : "max-w-[85%] self-start rounded-2xl rounded-bl-md bg-emerald-50 px-4 py-2.5 text-zinc-900 ring-1 ring-emerald-100"
            }
          >
            <span className="sr-only">{m.role === "you" ? "You: " : "Assistant: "}</span>
            {m.text}
            {m.gtin && (
              <>
                {" "}
                <Link href={`/p/${m.gtin}`} className="whitespace-nowrap font-medium underline">
                  See the product
                </Link>
              </>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
