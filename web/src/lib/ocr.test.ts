import { afterEach, describe, expect, it, vi } from "vitest";

const recognize = vi.fn<(image: unknown) => Promise<{ data: { text: string } }>>(async () => ({
  data: { text: "Calories 230" },
}));
const terminate = vi.fn(async () => {});
const createWorker = vi.fn(async () => ({ recognize, terminate }));
vi.mock("tesseract.js", () => ({ createWorker }));

import { readLabelText } from "./ocr";

afterEach(() => vi.unstubAllGlobals());

describe("[CONTRIB-1] label reading uses self-hosted Tesseract.js", () => {
  it("loads the worker, core and English data from /tesseract/ and shrinks the photo", async () => {
    const close = vi.fn();
    vi.stubGlobal("createImageBitmap", vi.fn(async () => ({ width: 4032, height: 3024, close })));
    const text = await readLabelText(new Blob(["x"]));
    expect(text).toBe("Calories 230");
    expect(createWorker).toHaveBeenCalledWith("eng", 1, {
      workerPath: "/tesseract/worker.min.js",
      corePath: "/tesseract",
      langPath: "/tesseract",
    });
    const canvas = recognize.mock.calls[0][0] as unknown as HTMLCanvasElement;
    expect([canvas.width, canvas.height]).toEqual([1600, 1200]);
    expect(close).toHaveBeenCalled();
    expect(terminate).toHaveBeenCalled(); // the worker is always released
  });
});
