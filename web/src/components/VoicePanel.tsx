"use client";

import { useEffect, useId, useRef, useState, useSyncExternalStore } from "react";

import { type PageData, answer, summary } from "@/lib/voice";

const CONSENT_KEY = "foodtrace.voice-consent"; // VOICE-7: remembered on this device only

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

// What the browser supports, as a stable string snapshot ("speech,mic"); none on the server.
function supportSnapshot(): string {
  return [
    typeof window !== "undefined" && "speechSynthesis" in window ? "speech" : "",
    recognitionCtor() ? "mic" : "",
  ].join(",");
}
const noSubscribe = () => () => {};

function readConsent(): boolean {
  try {
    return localStorage.getItem(CONSENT_KEY) === "yes";
  } catch {
    return false;
  }
}

// Ask about the product by voice or text, and hear it read aloud (spec 022).
export function VoicePanel({ data }: { data: PageData }) {
  const inputId = useId();
  const [question, setQuestion] = useState("");
  const [reply, setReply] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const [listening, setListening] = useState(false);
  const [askConsent, setAskConsent] = useState(false);
  const supported = useSyncExternalStore(noSubscribe, supportSnapshot, () => ",");
  const support = { speech: supported.startsWith("speech"), mic: supported.endsWith("mic") };
  const recognition = useRef<Recognition | null>(null);

  useEffect(() => {
    return () => {
      try {
        window.speechSynthesis?.cancel();
      } catch {}
    };
  }, []);

  function speak(text: string) {
    if (!support.speech) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "en-US";
      utterance.onend = () => setSpeaking(false);
      utterance.onerror = () => setSpeaking(false);
      setSpeaking(true);
      window.speechSynthesis.speak(utterance);
    } catch {
      setSpeaking(false); // VOICE-8
    }
  }

  function readAloud() {
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
    } else speak(summary(data)); // VOICE-5
  }

  function ask(q: string) {
    if (!q.trim()) return;
    const text = answer(q, data); // VOICE-6
    setReply(text);
    speak(text);
  }

  function listen() {
    const Ctor = recognitionCtor();
    if (!Ctor) return;
    if (!readConsent()) return setAskConsent(true); // VOICE-7
    try {
      const r = new Ctor();
      r.lang = "en-US";
      r.interimResults = false;
      r.onresult = (e) => {
        const heard = e.results[0]?.[0]?.transcript ?? "";
        setQuestion(heard);
        ask(heard);
      };
      r.onerror = () => setListening(false);
      r.onend = () => setListening(false);
      recognition.current = r;
      setListening(true);
      r.start();
    } catch {
      setListening(false); // VOICE-8
    }
  }

  function consent() {
    try {
      localStorage.setItem(CONSENT_KEY, "yes");
    } catch {}
    setAskConsent(false);
    listen();
  }

  return (
    <section aria-labelledby="voice-heading" className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 id="voice-heading" className="text-base font-semibold">
          Ask about this product
        </h2>
        {support.speech && (
          <button type="button" onClick={readAloud} className="btn-secondary px-3 py-1.5">
            {speaking ? "Stop" : "Read aloud"}
          </button>
        )}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
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
          placeholder="e.g. does it contain milk?"
          className="field min-w-0 flex-1 py-2"
        />
        {support.mic && (
          <button
            type="button"
            onClick={listening ? () => recognition.current?.stop() : listen}
            aria-pressed={listening}
            className="btn-secondary px-3 py-2"
          >
            {listening ? "Listening…" : "🎤"}
            <span className="sr-only">{listening ? "" : "Ask by voice"}</span>
          </button>
        )}
        <button type="submit" className="btn-primary px-3 py-2">
          Ask
        </button>
      </form>
      {askConsent && (
        <div role="alertdialog" aria-labelledby="mic-notice" className="rounded-lg bg-white p-3 text-sm ring-1 ring-zinc-300">
          <p id="mic-notice">
            Voice questions use your browser&apos;s speech service. In Chrome, your voice is sent to Google to turn it into
            text. You can type instead.
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
      <p aria-live="polite" className="text-sm">
        {reply}
      </p>
    </section>
  );
}
