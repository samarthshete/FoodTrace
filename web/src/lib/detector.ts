// Barcode detection: the native BarcodeDetector when the browser has one with our formats,
// otherwise the ZXing WebAssembly ponyfill served from our own origin (SCAN-3, SCAN-11).

export const FORMATS = ["ean_13", "ean_8", "upc_a"] as const;
export const WASM_PATH = "/zxing/zxing_reader.wasm";

export interface DetectorLike {
  detect(source: HTMLVideoElement): Promise<{ rawValue: string }[]>;
}

interface NativeDetectorCtor {
  new (opts: { formats: string[] }): DetectorLike;
  getSupportedFormats(): Promise<string[]>;
}

async function nativeDetector(): Promise<DetectorLike | null> {
  const Native = (globalThis as { BarcodeDetector?: NativeDetectorCtor }).BarcodeDetector;
  if (!Native) return null;
  const supported = await Native.getSupportedFormats().catch(() => [] as string[]);
  if (!FORMATS.every((f) => supported.includes(f))) return null;
  return new Native({ formats: [...FORMATS] });
}

export async function createDetector(): Promise<DetectorLike> {
  const native = await nativeDetector();
  if (native) return native;
  const { BarcodeDetector, prepareZXingModule } = await import("barcode-detector/ponyfill");
  prepareZXingModule({
    overrides: {
      locateFile: (path: string, prefix: string) =>
        path.endsWith(".wasm") ? WASM_PATH : prefix + path,
    },
  });
  return new BarcodeDetector({ formats: [...FORMATS] });
}
