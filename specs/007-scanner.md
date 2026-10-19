# 007: Scanner and manual entry

Status: implemented

The home page (`/`) gets a barcode into the app: by camera, or by typing it.

## Requirements

- **SCAN-1** The home page shows a "Scan a barcode" button and a manual entry field. Manual entry works without a camera.
- **SCAN-2** The camera starts only after the user taps "Scan a barcode". Nothing asks for camera permission on page load. It requests the rear camera (`facingMode: environment`).
- **SCAN-3** The detector looks for `ean_13`, `ean_8` and `upc_a` only. UPC-E is not decoded in v1 (spec 001, GTIN-6).
- **SCAN-4** Each camera read is validated in the browser with the same rules as spec 001. The TypeScript port is tested against the same examples. Invalid reads are ignored and scanning continues.
- **SCAN-5** A code is accepted only after the same valid code is read twice in a row, to filter misreads.
- **SCAN-6** On an accepted code the camera stops, the device vibrates briefly where supported, and the app navigates to `/p/<gtin13>`.
- **SCAN-7** If the camera is denied or unavailable, or barcode detection can't load, the scanner shows a plain message saying why and moves focus to manual entry.
- **SCAN-8** A torch button is shown only when the camera track reports torch support.
- **SCAN-9** Manual entry: invalid input shows the validation reason inline (linked to the field with `aria-describedby`) and does not navigate. Valid input navigates to `/p/<gtin13>`.
- **SCAN-10** The camera stream is stopped when the scanner closes or the page unmounts.
- **SCAN-11** The ZXing WebAssembly file is served from our own origin. Scanning makes no request to a third-party CDN.
