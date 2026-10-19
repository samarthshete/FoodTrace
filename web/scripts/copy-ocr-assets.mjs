// Copy Tesseract.js's worker, WASM cores and English data into public/tesseract/ so label
// reading never hits a CDN (spec 017, CONTRIB-1).
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";

const require = createRequire(import.meta.url);
const tesseractDir = dirname(dirname(require.resolve("tesseract.js")));
const fromTesseract = createRequire(require.resolve("tesseract.js"));
const coreDir = dirname(fromTesseract.resolve("tesseract.js-core/package.json"));
const engDir = dirname(require.resolve("@tesseract.js-data/eng/package.json"));
const outDir = join(import.meta.dirname, "..", "public", "tesseract");

mkdirSync(outDir, { recursive: true });
copyFileSync(join(tesseractDir, "dist", "worker.min.js"), join(outDir, "worker.min.js"));
// LSTM-only cores; Tesseract.js picks the fastest the browser supports.
for (const variant of ["", "-simd", "-relaxedsimd"]) {
  const file = `tesseract-core${variant}-lstm.wasm.js`;
  copyFileSync(join(coreDir, file), join(outDir, file));
}
copyFileSync(join(engDir, "4.0.0_best_int", "eng.traineddata.gz"), join(outDir, "eng.traineddata.gz"));
console.log("copied Tesseract.js worker, cores and eng data to public/tesseract/");
