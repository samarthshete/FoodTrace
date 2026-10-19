# 016: Search by product or brand name

Status: implemented

Search finds products already in our database (bulk-loaded or scanned before) by name or
brand, as the user types. It never calls Open Food Facts or USDA. A barcode typed into
search goes straight to the product page.

## `GET /search?q=&limit=`

- **SEARCH-1** `q` is trimmed and must be 2–100 characters. Otherwise the response is `422`
  problem+json. `limit` defaults to 10 and is clamped to 1–25.
- **SEARCH-2** A product matches when every word of `q` starts a word of its name or brand
  (full-text prefix match), or its name is similar to `q` (trigram similarity ≥ 0.3, for
  typos). Results are ordered by relevance: the full-text rank plus the name similarity,
  highest first. Ties go to products with a score, then by name.
- **SEARCH-3** If `q` is a valid barcode (spec 001), the response has `gtin` set to its
  GTIN-13 and `results` empty, so the client can open the product page. A barcode is
  never looked up live from search.
- **SEARCH-4** Each result has `gtin`, `name`, `brand`, `image_url`, and the current
  `engine_version` score's `total` and `band` (both `null` if not scored yet).
- **SEARCH-5** Words are reduced to letters and digits before matching, so punctuation and
  operators in `q` can't break the query. Accents in `q` are ignored (US product names are
  stored as written).
- **SEARCH-6** Responses carry `Cache-Control: public, max-age=300`.

## Search box on the home page

- **SEARCH-7** The home page has a "Search by name or brand" box. After 2 characters and a
  250 ms pause, it shows up to 8 suggestions with name, brand and score. It calls the API
  through the web app's `/api/search` route, so the API address stays server-side.
- **SEARCH-8** The box follows the ARIA combobox pattern: arrow keys move through the
  suggestions, Enter opens the highlighted one, Escape closes the list, and the number of
  results is announced. Choosing a suggestion opens `/p/{gtin}`.
- **SEARCH-9** A barcode typed into the box opens its product page on Enter (SEARCH-3). No
  results says "No products match". A failed search says "Search isn't available right
  now" and the scanner and manual entry still work.
- **SEARCH-10** Only the latest query's results are shown. A slow earlier response never
  replaces a newer one.

p95 latency is checked by hand on the loaded database (target ≤ 150 ms, PLAN M4).
