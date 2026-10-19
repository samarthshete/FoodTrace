# 006: Product lookup API

Status: implemented

## `GET /products/{gtin}`

- **LOOKUP-1** The path GTIN is normalized per spec 001. Invalid input → `422` with an RFC 9457 `application/problem+json` body whose `detail` says why.
- **LOOKUP-2** If the product is in Postgres and `fetched_at` is under `lookup.cache_days` (30) old, it is returned without any outbound call.
- **LOOKUP-3** On a miss or a stale row, the Open Food Facts v2 product API is called for each code in `lookup_forms(gtin)` (GTIN-8), in order, stopping at the first hit.
- **LOOKUP-4** Every outbound request sends `User-Agent: FoodTrace/<version> (<OFF_CONTACT>)`, with the contact taken from the environment.
- **LOOKUP-5** On HTTP 429 or 503, the client retries up to 2 times with exponential backoff (honouring `Retry-After` up to 5 s). Then it gives up and treats the source as unavailable.
- **LOOKUP-6** A product found live is upserted into `products` (keyed by the normalized GTIN, `source_by_field` set to `off` for every field it supplied), its additives into `product_additives`, and it is scored.
- **LOOKUP-7** Not found anywhere → `404` problem+json with `"next": "contribute"`.
- **LOOKUP-8** If OFF is unavailable and a stale row exists, the stale row is returned with `"stale": true`. If no row exists, the response is `503` problem+json.
- **LOOKUP-9** Scores are stored in `scores` keyed by `(gtin, engine_version)`. A score row is never updated across versions. If no row exists for the current version, one is computed and inserted.
- **LOOKUP-10** The response contains the product fields, the score (spec 005 output contract, without the breakdown), and `attribution: "Data from Open Food Facts (ODbL)"`.
- **LOOKUP-11** GET responses carry `Cache-Control: public, max-age=300` and an `ETag` built from the GTIN, `engine_version` and `fetched_at`. A matching `If-None-Match` gives `304`.

## `GET /products/{gtin}/breakdown`

- **LOOKUP-12** Returns the full score (spec 005 output contract, with the breakdown) and the `explain()` sentences. It uses the same lookup path as above, so an unknown product gives the same 404.

## Mapping Open Food Facts → `ProductFacts`

| ProductFacts | OFF field | Notes |
| --- | --- | --- |
| `energy_kj` | `nutriments.energy-kj_100g` | else `energy-kcal_100g × 4.184`, else `energy_100g` (kJ) |
| `sugars_g` | `sugars_100g` | |
| `saturated_fat_g` | `saturated-fat_100g` | |
| `fat_g` | `fat_100g` | |
| `salt_g` | `salt_100g` | else `sodium_100g × 2.5` |
| `fiber_g` | `fiber_100g` | |
| `proteins_g` | `proteins_100g` | |
| `fvl_percent` | `fruits-vegetables-legumes_100g` | else `fruits-vegetables-legumes-estimate-from-ingredients_100g`, flagged `estimated` |
| `nova_group` | `nova_group` | |
| additives | `additives_tags` | `None` when there is no `ingredients_text` and no `additives_tags` |

- **LOOKUP-13** The mapping follows the table above. Values that can't be parsed as numbers are treated as missing.

## Later

USDA FoodData Central live fallback (needs a free data.gov key in the environment) and
the bulk pipeline. Both get their own specs.
