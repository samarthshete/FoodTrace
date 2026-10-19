import { clientOf, createLimiter } from "@/lib/rate-limit";

// Speech to text for the assistant (spec 023, ASSIST-18): one recorded clip to Groq Whisper.
// Only the audio is sent, never stored. The text is then handled like a typed question.
const GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions";
const MAX_BYTES = 4 * 1024 * 1024;
const VOCABULARY = "Grocery products and brands, e.g. Pringles, Reese's, Cheerios, Kirkland, SPAM, Lay's, Oreo.";
const limited = createLimiter(20);

export function GET() {
  return Response.json({ enabled: !!process.env.GROQ_API_KEY });
}

function extension(type: string): string {
  if (type.includes("mp4") || type.includes("m4a") || type.includes("aac")) return "m4a";
  if (type.includes("ogg")) return "ogg";
  if (type.includes("wav")) return "wav";
  if (type.includes("mpeg")) return "mp3";
  return "webm";
}

export async function POST(request: Request) {
  const key = process.env.GROQ_API_KEY;
  if (!key) return Response.json({ detail: "Not configured." }, { status: 404 });
  let audio: FormDataEntryValue | null = null;
  try {
    audio = (await request.formData()).get("audio");
  } catch {
    audio = null;
  }
  if (!(audio instanceof Blob) || audio.size === 0) {
    return Response.json({ detail: "Send one recording as the audio field." }, { status: 400 });
  }
  if (audio.size > MAX_BYTES) return Response.json({ detail: "That recording is too long." }, { status: 413 });
  if (limited(clientOf(request))) return Response.json({ detail: "Too many questions." }, { status: 429 });

  const form = new FormData();
  form.set("file", audio, `question.${extension(audio.type)}`);
  form.set("model", process.env.GROQ_STT_MODEL || "whisper-large-v3-turbo");
  form.set("language", "en");
  form.set("temperature", "0");
  form.set("response_format", "json");
  form.set("prompt", VOCABULARY);
  try {
    const res = await fetch(GROQ_URL, {
      method: "POST",
      headers: { Authorization: `Bearer ${key}` },
      body: form,
      signal: AbortSignal.timeout(15_000),
    });
    if (!res.ok) throw new Error(`groq ${res.status}`);
    const text = ((await res.json()) as { text?: unknown }).text;
    if (typeof text !== "string" || !text.trim()) throw new Error("no speech");
    return Response.json({ text: text.trim().slice(0, 300) });
  } catch {
    return Response.json({ detail: "Couldn't transcribe that right now." }, { status: 503 });
  }
}
