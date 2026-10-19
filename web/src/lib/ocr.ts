// Read a label photo in the browser with Tesseract.js, self-hosted under /tesseract/
// (spec 017, CONTRIB-1). The photo never leaves the device.

export const MAX_SIDE = 1600;

/** Scale (w, h) down so the long side is at most MAX_SIDE. */
export function fitWithin(width: number, height: number, max = MAX_SIDE) {
  const scale = Math.min(1, max / Math.max(width, height));
  return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

async function shrink(file: Blob): Promise<HTMLCanvasElement> {
  const bitmap = await createImageBitmap(file);
  const { width, height } = fitWithin(bitmap.width, bitmap.height);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();
  return canvas;
}

export async function readLabelText(file: Blob): Promise<string> {
  const { createWorker } = await import("tesseract.js");
  const worker = await createWorker("eng", 1, {
    workerPath: "/tesseract/worker.min.js",
    corePath: "/tesseract",
    langPath: "/tesseract",
  });
  try {
    const { data } = await worker.recognize(await shrink(file));
    return data.text;
  } finally {
    await worker.terminate();
  }
}
