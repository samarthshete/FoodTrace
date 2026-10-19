# 008: Product page

Status: implemented

`/p/<gtin>` shows one product and its score. It reads only from the API (spec 006):
`GET /products/{gtin}` for product fields and `GET /products/{gtin}/breakdown` for the
breakdown and explanation. The UI never recomputes a score.

## Requirements

### Score

- **PAGE-1** The score shows as a number out of 100 plus the band label in text ("Good"). The band color is decorative; meaning never depends on color alone.
- **PAGE-2** Component bars for Nutrition, Additives and Processing show `value × weight` points out of `weight` (e.g. "36.7 of 60"), from `score.components`. A component that is `known: false` shows "No data", not 0, plus a note that the total was rescaled over the remaining components (spec 005, ENGINE-5).
- **PAGE-3** The Nutri-Score 2023 grade shows as a letter with the class it was scored as ("scored as a drink").
- **PAGE-4** The explanation sentences from the API are shown as a list.

### Details

- **PAGE-5** The breakdown lists every line grouped by component. Each line shows a readable label, the input value, the points, and a "Source" link to its `source_url`. Estimated lines are marked "Estimated".
- **PAGE-6** Additives show name and EFSA rating in words. Unrated additives say "Not rated by EFSA".
- **PAGE-15** Input values on breakdown lines are rounded as in ENGINE-13 (kJ whole, grams and % to 1 decimal, or 2 below 1).
- **PAGE-17** When the additives part is full marks but the product has additives, the bar says
  why: "None of its N additives has an EFSA risk rating." Full marks mean no rated risk, not
  no additives.
- **PAGE-16** A component with no breakdown lines says why: additives known with none found → "No additives found in the ingredient list."; unknown → "No data."
- **PAGE-7** A data badge comes from `confidence`: ≥ 0.9 "Complete data", ≥ 0.6 "Partial data", else "Limited data". Missing inputs are listed in words.
- **PAGE-8** Ingredients text is shown when present.

### States

- **PAGE-9** Not scored: the page says "Not scored" and why, and still shows additives and processing.
- **PAGE-10** Stale data (`stale: true`): a notice says the data is saved and couldn't be refreshed.
- **PAGE-11** API 404 → "We couldn't find this product" with a link back to scan. API 422 → the barcode error message. API 503 or network failure → "Try again" message. None of these crash the page.

### Every product page

- **PAGE-12** Footer: "Data from Open Food Facts (ODbL)" linking to openfoodfacts.org, and "Educational information, not medical advice."
- **PAGE-13** No user-facing copy in `web/src` contains "toxic", "dangerous" or "unsafe".
- **PAGE-14** The product page has no axe-detected WCAG 2.1 AA violations (Playwright e2e).

## PWA

- **PWA-1** The product is branded **FoodTrace**. A web app manifest uses `FoodTrace` as
  both its name and short name, uses `AI-Powered Grocery Intelligence Platform` as its
  description, and provides `start_url: /`, `display: standalone`, a theme color, and
  192 px and 512 px icons.
- **PWA-2** A service worker caches the app shell so the home page opens offline. Product data is never served from the service worker cache.
