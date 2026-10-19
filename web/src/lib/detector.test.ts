import { afterEach, describe, expect, it, vi } from "vitest";

const prepareZXingModule = vi.fn();
const ponyfillCtor = vi.fn();

vi.mock("barcode-detector/ponyfill", () => ({
  prepareZXingModule,
  BarcodeDetector: class {
    constructor(opts: unknown) {
      ponyfillCtor(opts);
    }
    detect() {
      return Promise.resolve([]);
    }
  },
}));

const { createDetector, FORMATS, WASM_PATH } = await import("./detector");

afterEach(() => {
  vi.clearAllMocks();
  delete (globalThis as { BarcodeDetector?: unknown }).BarcodeDetector;
});

describe("[SCAN-3] formats", () => {
  it("decodes EAN-13, EAN-8 and UPC-A only", () => {
    expect([...FORMATS]).toEqual(["ean_13", "ean_8", "upc_a"]);
  });

  it("passes exactly those formats to the ponyfill", async () => {
    await createDetector();
    expect(ponyfillCtor).toHaveBeenCalledWith({ formats: ["ean_13", "ean_8", "upc_a"] });
  });
});

describe("[SCAN-11] WebAssembly is served from our origin", () => {
  it("overrides locateFile so the .wasm comes from /zxing/", async () => {
    await createDetector();
    const { overrides } = prepareZXingModule.mock.calls[0][0];
    expect(overrides.locateFile("zxing_reader.wasm", "https://cdn.example/")).toBe(WASM_PATH);
    expect(WASM_PATH.startsWith("/")).toBe(true);
  });

  it("uses the native detector when it supports our formats, without loading WASM", async () => {
    const native = vi.fn();
    (globalThis as { BarcodeDetector?: unknown }).BarcodeDetector = class {
      static getSupportedFormats = () => Promise.resolve(["ean_13", "ean_8", "upc_a", "qr_code"]);
      constructor(opts: unknown) {
        native(opts);
      }
    };
    await createDetector();
    expect(native).toHaveBeenCalled();
    expect(prepareZXingModule).not.toHaveBeenCalled();
  });

  it("falls back to the ponyfill when the native detector lacks a format", async () => {
    (globalThis as { BarcodeDetector?: unknown }).BarcodeDetector = class {
      static getSupportedFormats = () => Promise.resolve(["qr_code"]);
    };
    await createDetector();
    expect(ponyfillCtor).toHaveBeenCalled();
  });
});
