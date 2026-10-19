# FoodTrace: web

**AI-Powered Grocery Intelligence Platform**

Next.js 16 PWA for FoodTrace: barcode scanner (`/scan`) and product page
(`/p/<gtin>`). Behaviour is specified in
`../specs/007-scanner.md` and `../specs/008-product-page.md`. See `../CLAUDE.md` for commands.

- Reads the API from `API_URL` (server-side), default `http://localhost:8000`.
- `pnpm install` copies the ZXing `.wasm` into `public/zxing/` so scanning never hits a CDN.
- The service worker (`public/sw.js`) caches the app shell only, never product data.
