import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DetectorLike } from "@/lib/detector";

import { ManualEntry } from "./ManualEntry";
import { Scanner } from "./Scanner";
import { ScanHome } from "./ScanHome";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

function fakeStream({ torch = false } = {}) {
  const track = {
    stop: vi.fn(),
    getCapabilities: () => (torch ? { torch: true } : {}),
    applyConstraints: vi.fn().mockResolvedValue(undefined),
  };
  const stream = { getTracks: () => [track], getVideoTracks: () => [track] };
  return { stream: stream as unknown as MediaStream, track };
}

function detectorReading(...codes: string[]): () => Promise<DetectorLike> {
  let i = 0;
  return async () => ({
    detect: async () => [{ rawValue: codes[Math.min(i++, codes.length - 1)] }],
  });
}

afterEach(() => vi.clearAllMocks());

describe("[SCAN-1] home page", () => {
  it("offers both the scan button and manual entry", () => {
    render(<ScanHome />);
    expect(screen.getByRole("button", { name: "Scan a barcode" })).toBeInTheDocument();
    expect(screen.getByLabelText("Or type the barcode number")).toBeInTheDocument();
  });

  it("manual entry works without any camera", async () => {
    render(<ScanHome />);
    await userEvent.type(screen.getByLabelText("Or type the barcode number"), "036000291452");
    await userEvent.click(screen.getByRole("button", { name: "Look up" }));
    expect(push).toHaveBeenCalledWith("/p/0036000291452");
  });
});

describe("[SCAN-2] camera starts only on tap", () => {
  it("does not request the camera on render, then asks for the rear camera", async () => {
    const gum = vi.fn().mockResolvedValue(fakeStream().stream);
    render(<Scanner onDetected={vi.fn()} getUserMedia={gum} createDetector={detectorReading("x")} />);
    expect(gum).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Scan a barcode" }));
    expect(gum).toHaveBeenCalledWith({
      video: { facingMode: { ideal: "environment" } },
      audio: false,
    });
  });
});

describe("[SCAN-5] [SCAN-6] accepting a code", () => {
  it("navigates after two identical reads, stops the camera and vibrates", async () => {
    const { stream, track } = fakeStream();
    const onDetected = vi.fn();
    const vibrate = vi.fn();
    Object.defineProperty(navigator, "vibrate", { value: vibrate, configurable: true });
    render(
      <Scanner
        onDetected={onDetected}
        getUserMedia={vi.fn().mockResolvedValue(stream)}
        createDetector={detectorReading("036000291453", "036000291452", "036000291452")}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Scan a barcode" }));
    await waitFor(() => expect(onDetected).toHaveBeenCalledWith("0036000291452"));
    expect(onDetected).toHaveBeenCalledTimes(1);
    expect(track.stop).toHaveBeenCalled();
    expect(vibrate).toHaveBeenCalled();
  });
});

describe("[SCAN-7] camera problems", () => {
  it.each([
    ["NotAllowedError", "Camera access is blocked"],
    ["NotFoundError", "No camera was found"],
  ])("%s shows a message and focuses manual entry", async (name, message) => {
    const gum = vi.fn().mockRejectedValue(Object.assign(new Error(name), { name }));
    render(
      <>
        <Scanner onDetected={vi.fn()} getUserMedia={gum} createDetector={detectorReading("x")} />
        <ManualEntry onSubmit={vi.fn()} />
      </>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Scan a barcode" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByLabelText("Or type the barcode number")).toHaveFocus();
  });

  it("explains when barcode detection can't load", async () => {
    render(
      <Scanner
        onDetected={vi.fn()}
        getUserMedia={vi.fn()}
        createDetector={() => Promise.reject(new Error("wasm failed"))}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Scan a barcode" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("isn't available in this browser");
  });
});

describe("[SCAN-8] torch", () => {
  it("shows the light button only when the track supports torch", async () => {
    const { stream, track } = fakeStream({ torch: true });
    render(
      <Scanner
        onDetected={vi.fn()}
        getUserMedia={vi.fn().mockResolvedValue(stream)}
        createDetector={detectorReading("x")}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Scan a barcode" }));
    const light = await screen.findByRole("button", { name: "Light on" });
    await userEvent.click(light);
    expect(track.applyConstraints).toHaveBeenCalledWith({ advanced: [{ torch: true }] });
  });

  it("hides the light button without torch support", async () => {
    render(
      <Scanner
        onDetected={vi.fn()}
        getUserMedia={vi.fn().mockResolvedValue(fakeStream().stream)}
        createDetector={detectorReading("x")}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Scan a barcode" }));
    await screen.findByRole("button", { name: "Stop scanning" });
    expect(screen.queryByRole("button", { name: /Light/ })).toBeNull();
  });
});

describe("[SCAN-10] camera is released", () => {
  it("stops tracks on unmount", async () => {
    const { stream, track } = fakeStream();
    const { unmount } = render(
      <Scanner
        onDetected={vi.fn()}
        getUserMedia={vi.fn().mockResolvedValue(stream)}
        createDetector={detectorReading("x")}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Scan a barcode" }));
    await screen.findByRole("button", { name: "Stop scanning" });
    unmount();
    expect(track.stop).toHaveBeenCalled();
  });

  it("stops tracks when the user taps Stop scanning", async () => {
    const { stream, track } = fakeStream();
    render(
      <Scanner
        onDetected={vi.fn()}
        getUserMedia={vi.fn().mockResolvedValue(stream)}
        createDetector={detectorReading("x")}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Scan a barcode" }));
    await userEvent.click(await screen.findByRole("button", { name: "Stop scanning" }));
    expect(track.stop).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Scan a barcode" })).toBeInTheDocument();
  });
});

describe("[SCAN-9] manual entry validation", () => {
  it("shows the reason inline, linked to the field, and does not submit", async () => {
    const onSubmit = vi.fn();
    render(<ManualEntry onSubmit={onSubmit} />);
    const input = screen.getByLabelText("Or type the barcode number");
    await userEvent.type(input, "036000291453");
    await userEvent.click(screen.getByRole("button", { name: "Look up" }));
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("check digit");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.getAttribute("aria-describedby")).toBe(alert.id);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits the normalized GTIN-13", async () => {
    const onSubmit = vi.fn();
    render(<ManualEntry onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("Or type the barcode number"), "96385074");
    await userEvent.click(screen.getByRole("button", { name: "Look up" }));
    expect(onSubmit).toHaveBeenCalledWith("0000096385074");
  });
});
