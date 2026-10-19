# FoodTrace: Technical Spec

**AI-Powered Grocery Intelligence Platform**

Source of truth for *what* to build. `docs/PLAN.md` says *in what order*.

## 1. Scope

**MVP goals**
- Scan or type a US barcode and get a scored product page in under 3 s.
- Deterministic, explainable scoring: every rule applied is listed with its source.
- Layered lookup: Postgres cache → Open Food Facts → USDA → label-photo fallback.
- Accounts with scan history, favorites, and allergen/diet flags.
- $0/month infrastructure, with no lock-in to proprietary provider features.

**Non-goals (MVP):** cosmetics scoring (phase 2), native apps, medical or condition-specific advice, non-US coverage, LLM-generated scores or health claims.

## 2. Requirements

| ID | Functional requirement |
| --- | --- |
| F1 | Camera barcode scan in mobile Safari and Chrome, with manual entry as a fallback |
| F2 | Normalize to GTIN-13 and validate the check digit before lookup |
| F3 | Product page: score, color band, per-component breakdown, ingredients, additives with evidence grade and US regulatory status |
| F4 | Data completeness badge; "not scored" when required inputs are missing |
| F5 | Alternatives: higher-scored products in the same category |
| F6 | Search-as-you-type by product or brand name |
| F7 | Label-photo contribution: extract, user confirms, save, push to OFF |
| F8 | User allergens/diets flag conflicts on the product page |
| F9 | Recall banner when an openFDA enforcement record matches brand + product |
| F10 | Voice question about the scanned product (phase 1.5) |

| Area | Non-functional target |
| --- | --- |
| Latency | p95 ≤ 300 ms on a cache hit; ≤ 2.5 s with a live OFF/USDA fallback |
| Coverage | ≥ 85% of scanned US barcodes resolved without the photo flow |
| Correctness | Our Nutri-Score grade matches OFF's on ≥ 99% of the golden set |
| Reproducibility | Same inputs + `engine_version` → identical score |
| Footprint | Hosted DB ≤ 450 MB |
| Accessibility | WCAG 2.1 AA; product page readable aloud |
| Privacy | History deletable in one call; RLS per user |

## 3. Data sources

| Source | Use | Access | License |
| --- | --- | --- | --- |
| Open Food Facts product DB | Products: ingredients, nutriments, NOVA, categories, labels, images | `https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz` (~1.3 GB, refreshed daily) + live API | ODbL: attribution; a published derived DB must stay ODbL |
| OFF taxonomies | Additives (E-number → name, class, EFSA evaluation, ADI, overexposure risk), ingredients, categories, labels, allergens | OFF taxonomy files / API; Python SDK `openfoodfacts` (MIT) | ODbL |
| USDA FoodData Central: Branded | US UPCs with label nutrition + ingredient text (~2M) | CSV download from fdc.nal.usda.gov/download-datasets + REST API (free data.gov key) | CC0; cite "USDA FoodData Central" |
| EFSA OpenFoodTox | Reference values (ADI/NOAEL) + link to the EFSA opinion | Download (EFSA Knowledge Junction / Zenodo) | Re-use allowed with EFSA acknowledged |
| FDA Substances Added to Food | US status: GRAS, approved, prohibited (21 CFR 189), delisted colors | Excel download from fda.gov | US government work |
| openFDA food enforcement | Recall records for the product page banner | `https://api.fda.gov/food/enforcement.json` | Public. Not a live alert feed: show "related recall on record" |
| Robotoff (OFF ML) | Nutrition-table extraction from label photos | Robotoff API | Open source |
| Phase 2: Open Beauty Facts, EU CosIng | Cosmetics + INCI ingredient regulation | `beauty.parquet` (~42 MB) / EU Open Data Portal | ODbL / EU open data |

**Before writing any import code, inspect the actual schema:** read the export's CSV header (`gunzip -c … | head -1`) and the USDA CSV headers. Column names in this spec are targets, not guarantees.

## 4. Architecture

```
Browser (PWA): barcode scan (WASM) · label OCR · voice
        │  GTIN
        ▼
API (FastAPI): lookup service ─► scoring engine ─► response
        │  read/write                 ▲
        ▼                             │ on cache miss
PostgreSQL (products, scores, users)  Live APIs: OFF · USDA · openFDA · Robotoff
        ▲
        │ bulk upsert + re-score (weekly, GitHub Actions)
Offline pipeline: OFF CSV export + USDA CSV + taxonomies/EFSA/FDA → Polars (filter US, merge, dedupe)
```

### Lookup flow (`GET /products/{gtin}`)
1. Normalize to GTIN-13 and validate. Invalid → 422.
2. Postgres hit and `fetched_at` < 30 days → return the product + the current-version score.
3. Miss or stale → OFF live API (try 13- and 12-digit forms) → USDA FDC API (`gtinUpc`). Upsert, score, return.
4. Still missing → 404 with `{"next": "contribute"}`. The client opens the label-photo flow.

### Pipeline (`pipeline/run.py --country us`)
1. **OFF:** filter rows where `countries_tags` contains `en:united-states` AND (nutriments present OR ingredients present). Select only the scoring fields + name, brand, categories, labels, one image URL.
2. **USDA:** join branded foods to nutrients by `fdc_id`, normalize `gtin_upc` to GTIN-13, keep the latest record per GTIN.
3. **Merge** on GTIN: per field, keep the more complete value; record `source_by_field`.
4. **Reference data:** additives (OFF taxonomy ⨝ OpenFoodTox ⨝ FDA status), keyed by E-number/name.
5. **Load:** `COPY` into staging tables, swap in a transaction, re-score changed rows.
6. Print a size report. Fail the run if the DB would exceed 450 MB.

## 5. Data model

```sql
products(gtin TEXT PK, name, brand, primary_category, categories TEXT[], image_url,
         ingredients_text, nutrition JSONB,           -- per 100 g/ml: {field: {value, estimated}}
         nova_group SMALLINT, labels TEXT[], is_organic BOOL,
         additives_known BOOL,                        -- false = additive list unknown (spec 003 ADD-6)
         source_by_field JSONB, completeness NUMERIC(3,2), fetched_at TIMESTAMPTZ)
-- The Nutri-Score class (general/beverage/cheese/fats/water) is derived from categories
-- at scoring time (spec 002 NS-1). primary_category is for alternatives.
additives(code TEXT PK, name, class, risk_level SMALLINT, evidence_grade TEXT,
          adi_mg_kg NUMERIC, us_status TEXT, efsa_url, fda_cfr_ref, overexposure_risk TEXT)
product_additives(gtin FK, additive_code FK, PRIMARY KEY (gtin, additive_code))
scores(gtin FK, engine_version TEXT, total SMALLINT, nutrition_pts NUMERIC,
       additive_pts NUMERIC, processing_pts NUMERIC, breakdown JSONB,
       computed_at TIMESTAMPTZ, PRIMARY KEY (gtin, engine_version))
-- The tables below arrive in M5. Better Auth (Google sign-in) owns the auth tables and uses
-- TEXT user ids, so user_id columns are TEXT. RLS policies key on current_setting('app.user_id').
users(id TEXT PK, email, allergens TEXT[], diets TEXT[])
scan_history(id BIGSERIAL, user_id FK, gtin FK, scanned_at)       -- RLS: user_id = auth user
favorites(user_id FK, gtin FK, PRIMARY KEY (user_id, gtin))       -- RLS
contributions(id, user_id FK, gtin, photo_url, extracted JSONB, status TEXT, created_at)
```
Indexes: GIN trigram on `products.name` and `products.brand`; a GIN `tsvector` over name + brand; B-tree on `products.category`.

## 6. API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/products/{gtin}` | Layered lookup; product + score |
| GET | `/products/{gtin}/breakdown` | Every rule applied, with sources |
| GET | `/products/{gtin}/alternatives` | Higher-scored items in the same category (top 5) |
| GET | `/search?q=&limit=` | Trigram + full-text autocomplete |
| POST | `/contributions` | Label photo + extracted fields (user-confirmed) |
| GET / DELETE | `/me/history` | Scan history; DELETE wipes all |
| PUT | `/me/preferences` | Allergens, diets |
| POST | `/voice/query` | Text in → answer built only from the calls above (phase 1.5) |

Design rules: resources are nouns; GTIN is the key; GETs are cacheable (`Cache-Control` + ETag on the score version); writes touch only user data; errors use RFC 9457 problem+json.

## 7. Scoring engine

```
score = 60·N + 30·A + 10·P,   N, A, P ∈ [0, 1]
```

| Component | Input | Mapping |
| --- | --- | --- |
| N: Nutrition (60) | **Nutri-Score 2023** (foods) / 2024 (beverages) points, by category: general, beverage, cheese, fats/oils/nuts/seeds | Linear map of points onto 0–1 within the category's range |
| A: Additives (30) | Per additive: `risk_level` × `evidence_grade` | Start at 1, subtract per additive. A high-risk + strong-evidence additive caps the total score |
| P: Processing (10) | NOVA group 1–4 | 1 → 1.0, 2 → 0.67, 3 → 0.33, 4 → 0. Organic is an info badge, not points (open question) |

- **Implementation:** port the Nutri-Score 2023 logic from the Open Food Facts `ProductOpener::Nutriscore` documentation (the `_2023` functions). Do not copy its AGPL code. Every threshold lives in `config/scoring.yaml`.
- **Golden test:** sample ≥ 2,000 OFF products that have `nutriscore_grade` and full nutriments. Our grade must match on ≥ 99%. Mismatches get written to a report for inspection.
- **Estimated fields:** fruit/veg/legume % comes from ingredient text when missing, flagged `estimated: true` in the breakdown.
- **Not scored:** if energy, sugars, saturated fat, or salt is missing, return the additives-only view and `total: null`.
- **Additive grades** come from data: OFF/EFSA overexposure risk + ADI (OpenFoodTox) + FDA status. Each breakdown line links its `source_url`.
- **Score bands (for color):** 0–24 poor, 25–49 mediocre, 50–74 good, 75–100 excellent (configurable). Every band shows its label in text as well as color.

## 8. Hosting ($0)

| Piece | Host | Guardrail |
| --- | --- | --- |
| Web | Vercel or Cloudflare Pages free | No card on file |
| API | Render free tier, or a home machine + Cloudflare Tunnel | Cold starts accepted |
| DB | Supabase free (500 MB, pauses after 7 idle days) | ≤ 450 MB; weekly cron keeps it awake |
| Photos | Supabase Storage (1 GB) | Compress to < 300 KB; delete after extraction |
| CI/cron | GitHub Actions | Public repo |

Everything must also run locally via `docker compose up` with no external accounts.

## 9. Legal & copy

- Attribution footer on every product page: "Data from Open Food Facts (ODbL) and USDA FoodData Central." Also an About page.
- Methodology page plus a changelog for every `engine_version`.
- Footer: "Educational information, not medical advice."
- Recall copy: "A related FDA recall is on record" + link. Never "this product is recalled".

## 10. Open questions

- ~~Repo license: MIT or AGPL?~~ MIT (decided 2026-10-12). Data stays ODbL/CC0.
- Organic: info badge only (current default) or a small bonus?
- Supabase or Neon for hosted Postgres?
- Phase 2 order: cosmetics or Open Prices?
