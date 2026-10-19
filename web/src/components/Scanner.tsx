"use client";

import { useEffect, useRef, useState } from "react";

import { createDetector as defaultCreateDetector, type DetectorLike } from "@/lib/detector";
import { createReadFilter } from "@/lib/gtin";

import { MANUAL_INPUT_ID } from "./ManualEntry";

const SCAN_INTERVAL_MS = 150;

type TorchCapabilities = MediaTrackCapabilities & { torch?: boolean };

export function cameraErrorMessage(error: unknown): string {
  const name = error instanceof DOMException || error instanceof Error ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "Camera access is blocked. You can type the barcode number below instead.";
  }
  if (name === "NotFoundError" || name === "OverconstrainedError" || name === "NoCamera") {
    return "No camera was found. You can type the barcode number below instead.";
  }
  if (name === "NoDetector") {
    return "Barcode scanning isn't available in this browser. You can type the number below.";
  }
  return "The camera couldn't start. You can type the barcode number below instead.";
}

function namedError(name: string): Error {
  const e = new Error(name);
  e.name = name;
  return e;
}

export function Scanner({
  onDetected,
  createDetector = defaultCreateDetector,
  getUserMedia,
}: {
  onDetected: (gtin: string) => void;
  createDetector?: () => Promise<DetectorLike>;
  getUserMedia?: (c: MediaStreamConstraints) => Promise<MediaStream>;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [active, setActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [torchSupported, setTorchSupported] = useState(false);
  const [torchOn, setTorchOn] = useState(false);

  function stop() {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setActive(false);
    setTorchOn(false);
    setTorchSupported(false);
  }

  useEffect(() => stop, []); // SCAN-10: release the camera on unmount

  async function start() {
    setError(null);
    try {
      const gum =
        getUserMedia ??
        (navigator.mediaDevices?.getUserMedia
          ? (c: MediaStreamConstraints) => navigator.mediaDevices.getUserMedia(c)
          : null);
      if (!gum) throw namedError("NoCamera");
      const detector = await createDetector().catch(() => {
        throw namedError("NoDetector");
      });
      const stream = await gum({ video: { facingMode: { ideal: "environment" } }, audio: false });
      streamRef.current = stream;
      const track = stream.getVideoTracks()[0];
      const caps = (track?.getCapabilities?.() ?? {}) as TorchCapabilities;
      setTorchSupported(caps.torch === true); // SCAN-8
      setActive(true);

      const video = videoRef.current;
      if (video) {
        video.srcObject = stream;
        try {
          await video.play();
        } catch {
          // Autoplay can be refused; muted inline video usually plays, and detection still works.
        }
      }
      const accept = createReadFilter();
      const tick = async () => {
        if (!streamRef.current || !videoRef.current) return;
        try {
          const codes = await detector.detect(videoRef.current);
          for (const code of codes) {
            const gtin = accept(code.rawValue); // SCAN-4, SCAN-5
            if (gtin) {
              stop();
              navigator.vibrate?.(80); // SCAN-6
              onDetected(gtin);
              return;
            }
          }
        } catch {
          // A frame that can't be decoded is normal; keep scanning.
        }
        timerRef.current = setTimeout(tick, SCAN_INTERVAL_MS);
      };
      void tick();
    } catch (e) {
      stop();
      setError(cameraErrorMessage(e)); // SCAN-7
      document.getElementById(MANUAL_INPUT_ID)?.focus();
    }
  }

  async function toggleTorch() {
    const track = streamRef.current?.getVideoTracks()[0];
    if (!track) return;
    const next = !torchOn;
    await track
      .applyConstraints({ advanced: [{ torch: next } as MediaTrackConstraintSet] })
      .then(() => setTorchOn(next))
      .catch(() => setTorchSupported(false));
  }

  return (
    <section aria-label="Barcode scanner" className="flex flex-col gap-3">
      <div
        className={`relative overflow-hidden rounded-2xl bg-black ${active ? "aspect-[3/4]" : "hidden"}`}
      >
        <video ref={videoRef} muted playsInline className="h-full w-full object-cover" />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-8 top-1/2 h-24 -translate-y-1/2 rounded-lg border-2 border-white/80"
        />
      </div>
      {active ? (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={stop}
            className="btn-secondary flex-1"
          >
            Stop scanning
          </button>
          {torchSupported && (
            <button
              type="button"
              onClick={toggleTorch}
              aria-pressed={torchOn}
              className="btn-secondary"
            >
              {torchOn ? "Light off" : "Light on"}
            </button>
          )}
        </div>
      ) : (
        <button
          type="button"
          onClick={start}
          className="btn-accent w-full py-4 text-base"
        >
          Scan a barcode
        </button>
      )}
      {active && <p className="text-sm text-zinc-600">Point the camera at the barcode.</p>}
      {error && (
        <p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
          {error}
        </p>
      )}
    </section>
  );
}
