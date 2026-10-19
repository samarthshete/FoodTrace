// Records one short clip from the microphone (spec 023, ASSIST-19). Browser only.
export interface Recording {
  /** Stops and resolves with the clip. */
  stop(): Promise<Blob>;
}

export function canRecord(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.MediaRecorder !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia
  );
}

/** Asks for the mic (the browser shows its own prompt) and starts recording. */
export async function startRecording(): Promise<Recording> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const type = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((t) => MediaRecorder.isTypeSupported(t));
  const recorder = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
  const chunks: Blob[] = [];
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };
  recorder.start();
  return {
    stop: () =>
      new Promise<Blob>((resolve) => {
        recorder.onstop = () => {
          stream.getTracks().forEach((t) => t.stop()); // turn the mic light off
          resolve(new Blob(chunks, { type: recorder.mimeType || type || "audio/webm" }));
        };
        if (recorder.state === "inactive") recorder.onstop(new Event("stop"));
        else recorder.stop();
      }),
  };
}

/** Sends the clip to our route; null on any failure. */
export async function transcribe(clip: Blob): Promise<string | null> {
  try {
    const form = new FormData();
    form.set("audio", clip);
    const res = await fetch("/api/assistant/transcribe", { method: "POST", body: form });
    if (!res.ok) return null;
    const text = ((await res.json()) as { text?: string }).text;
    return text?.trim() || null;
  } catch {
    return null;
  }
}

/** Whether the server has a Groq key (GET /api/assistant/transcribe). */
export async function whisperEnabled(): Promise<boolean> {
  try {
    const res = await fetch("/api/assistant/transcribe");
    return res.ok && ((await res.json()) as { enabled?: boolean }).enabled === true;
  } catch {
    return false;
  }
}
