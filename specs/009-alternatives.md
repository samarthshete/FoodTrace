# 009: Alternatives

Status: implemented

The product page suggests up to five better-scored products from the same category (SPEC F5).
Alternatives come only from products already in our database. Until the bulk pipeline lands,
that is the products people have scanned, so the list is often empty, and that is expected.

## `GET /products/{gtin}/alternatives`

- **ALT-1** The base product is resolved with the same lookup path as spec 006, so an invalid,
  unknown or unreachable product gives the same `422`, `404` or `503`.
- **ALT-2** Candidates are products whose current-`engine_version` score has `status: scored`
  and `confidence ≥ 0.6`. A "Limited data" product is never recommended.
- **ALT-3** Candidates are in the same Nutri-Score class as the base product (general, beverage,
  cheese, fats/oils/nuts/seeds, water), so a drink never suggests a food.
- **ALT-4** Category match: candidates must have the base product's `primary_category` in their
  `categories`. If that gives no results, the next two less specific categories from the base
  product's `categories` list are tried in turn, most specific first. Broader categories are
  never used. The response says which category matched.
- **ALT-5** If the base product is scored, a candidate's total must be at least
  `alternatives.min_gain` (5) points higher than the base product's total. If the base product is
  not scored, candidates are not compared to it. The best-scored ones in the category are shown.
- **ALT-6** At most `alternatives.limit` (5) results are returned, ordered by total (highest
  first), then confidence (highest first), then GTIN. The base product is never included.
- **ALT-7** Each result has `gtin`, `name`, `brand`, `image_url`, `total`, `band` and
  `confidence`. The response has `gtin`, `category` (the one matched, or `null`),
  `alternatives` and `attribution`.
- **ALT-8** No category, or no candidates → `200` with an empty `alternatives` list, never an
  error.
- **ALT-9** The response carries `Cache-Control: public, max-age=300`. There is no ETag, because
  the list changes whenever other products are added.

## Product page

- **ALT-10** The product page shows a "Better-scored alternatives" strip below the score
  summary when the list is not empty. Each item shows its name, brand, image, score out of 100
  and band label in words, and links to `/p/{gtin}`.
- **ALT-11** When the list is empty, the strip is not shown. A failed alternatives request also
  hides the strip and never breaks the product page.
- **ALT-12** The strip names the matched category in words, built from the category tag:
  `en:breakfast-cereals` → "In breakfast cereals".

## Config

`alternatives.min_gain` and `alternatives.limit` live in `config/scoring.yaml` under
`alternatives:`. They don't change any score, so changing them does not bump `engine_version`.
