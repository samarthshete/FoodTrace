// Copy the ZXing reader WebAssembly into public/ so scanning never hits a CDN (spec 007, SCAN-11).
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(import.meta.url);
// zxing-wasm is a dependency of barcode-detector, so resolve it from there (pnpm is strict).
const fromDetector = createRequire(require.resolve("barcode-detector/ponyfill"));
const entry = fromDetector.resolve("zxing-wasm/reader");
const packageRoot = entry.slice(0, entry.lastIndexOf("/zxing-wasm/") + "/zxing-wasm".length);
const readerDir = join(packageRoot, "dist", "reader");
const outDir = join(import.meta.dirname, "..", "public", "zxing");

mkdirSync(outDir, { recursive: true });
copyFileSync(join(readerDir, "zxing_reader.wasm"), join(outDir, "zxing_reader.wasm"));
console.log("copied zxing_reader.wasm to public/zxing/");
