# Build Plan

Work top to bottom. Finish a milestone's acceptance criteria before starting the next one. Tick tasks as they land. Two gates (⛳) can change scope: stop and report the numbers before moving on.

Every task follows the spec-driven workflow in `specs/README.md`: spec first, then spec-tagged tests, then code.

**Order changed (2026-10-12):** the core is built first: barcode → live OFF lookup → score → product page. The bulk pipeline (rest of M1) moves after the M3 product page, and its tool is not chosen yet. Accounts with Google sign-in come last (M5).

## M0: Repo scaffold (day 1)

- [x] `git init`, `.gitignore` (data/, .env, node_modules, .venv), MIT/AGPL LICENSE placeholder (license is an open question)
- [x] `uv` project with `pipeline` and `api` packages; ruff, mypy, pytest configured
- [x] `docker-compose.yml`: Postgres 16 with `pg_trgm` enabled, a named volume, healthcheck
- [x] Alembic set up; first migration creates the tables in SPEC §5 (auth tables come later)
- [x] `config/scoring.yaml` skeleton with `engine_version: "0.1.0"`
- [x] GitHub Actions: lint + test on PR (Postgres service container)
- [x] `web/`: Next.js + TS + Tailwind scaffold (empty page), pnpm, eslint *(moved to M3)*

**Done when:** `docker compose up -d db && uv run alembic upgrade head && uv run pytest` passes on a clean clone, and CI is green.

## M1: Data foundation (weeks 1–2)

- [x] `pipeline/off_bulk.py`: download the OFF CSV export to `data/off/` (skip if present); record the real column names in a comment; filter to US + scorable rows; select the needed fields *(spec 011; Polars, not DuckDB)*
- [x] `pipeline/usda_bulk.py`: read Branded Foods CSVs straight from the zip in `data/usda/` (headers inspected); pivot the needed nutrients per 100 g; normalize `gtin_upc` *(spec 012)*
- [x] `api/app/services/gtin.py`: normalize + validate GTIN (UPC-A, EAN-8, EAN-13), with unit tests covering bad check digits, leading zeros, and 12↔13 forms
- [x] Per-field merge on GTIN, with `source_by_field` and a `completeness` score *(USDA fills OFF gaps, never replaces; in `usda_mapping.fill_gaps`)*
- [x] `pipeline/reference.py`: build the `additives` table from the OFF additives taxonomy + FDA Substances Added to Food *(spec 013; OpenFoodTox is CC BY-ND, so not imported: ADIs come from the OFF taxonomy)*
- [x] `pipeline/load.py`: staging table → `COPY` → merge in a transaction (keeps newer live rows); size report; fail above 450 MB
- [x] `GET /products/{gtin}`: cache → OFF live → USDA live → 404 `{"next":"contribute"}`; upsert on fetch; descriptive User-Agent; backoff on 429 *(spec 006; USDA live fallback in spec 012)*
- [x] Integration tests for each branch of the lookup flow (mock HTTP with `respx`)

**⛳ Coverage gate:** collect ~200 real US barcodes (pantry, receipts, a grocery run) into `data/coverage_sample.txt`. Report the % resolved by cache + live APIs. If < 85%, narrow to the top grocery categories and note it in SPEC before continuing.

**Done when:** a pipeline run loads the US subset under 450 MB, the lookup endpoint passes its tests, and the coverage number is reported.

## M2: Scoring engine (weeks 3–4)

- [x] `scoring/nutriscore_2023.py`: port the 2023 algorithm (general, beverages, cheese, fats/oils/nuts/seeds) from OFF's `ProductOpener::Nutriscore` docs; thresholds in `config/scoring.yaml`
- [x] Fruit/veg/legume % estimator from ingredient text, flagged `estimated` *(spec 014; a lower bound from stated percentages)*
- [x] `scoring/additives.py`: penalty from `risk_level` × `evidence_grade`; cap rule for high-risk + strong-evidence
- [x] `scoring/processing.py`: NOVA → 0–1; derive NOVA from ingredient markers when missing *(spec 014; 91% agreement with OFF on 20,000 US products)*
- [x] `scoring/engine.py`: combine into a 0–100 total + breakdown list `[{rule_id, points, input_value, source_url, estimated}]`; "not scored" path
- [x] `scoring/explain.py`: template sentences from the breakdown (no LLM)
- [x] `GET /products/{gtin}/breakdown`; scores persisted per `engine_version`; pipeline re-scores on load *(spec 011, OFF-8)*
- [x] Unit test per rule, plus property tests (score always 0–100, deterministic)

**⛳ Golden gate:** sample ≥ 2,000 OFF products with `nutriscore_grade` + full nutriments. Our grade matches on ≥ 99%. Write mismatches to `reports/golden_mismatches.csv`.

✅ **Passed 2026-10-12** (spec 015): 41,750 US products, **99.27%** match after fixing two porting bugs (water class, olive/rapeseed/walnut oils). CI enforces ≥ 99% on a committed 3,000-product sample.

**Done when:** the golden gate passes, and every breakdown line has a rule id and a source.

## M3: Scanner + product page (weeks 5–6)

- [x] PWA manifest + service worker (offline shell only); installable on iOS/Android
- [x] Scanner page: `barcode-detector` polyfill, camera permission UX, torch toggle where supported, manual entry fallback
- [x] Product page: score + band (text label + color), component bars, breakdown list with source links, ingredients, additives (grade + US status), completeness badge, attribution + "not medical advice" footer *(US regulatory status from FDA, spec 013)*
- [x] `GET /products/{gtin}/alternatives` + an alternatives strip *(fills up once the bulk pipeline loads products)*
- [x] Recall banner from openFDA (synced from the bulk file, matched on barcode or brand + product name) *(daily GitHub Actions sync, spec 020; runs once the DATABASE_URL secret is set)*
- [x] Playwright e2e: scan-by-entry → product page → breakdown → alternative *(axe check, offline shell and recall banner also covered)*

**Done when:** scan-to-result is under 3 s on a mid-range phone over 4G (cache hit), and axe reports no WCAG 2.1 AA violations on the product page.

## M4: Search + contributions (week 7)

- [x] `GET /search?q=`: trigram + tsvector ranking, debounced client autocomplete *(spec 016; p95 still to measure on the loaded DB)*
- [x] Label-photo flow: capture → compress → Tesseract.js in the browser → user confirms every field → `POST /contributions` → score *(spec 017; Robotoff only works on photos already on OFF)*
- [x] Opt-in push of confirmed data back to OFF *(spec 017; needs OFF_USER/OFF_PASSWORD; photos not uploaded in v1)*

**Done when:** p95 search latency is ≤ 150 ms on the loaded subset, and a missing product can be added and scored end to end.

## M5: Accounts (week 8)

- [x] Better Auth with Google sign-in; session in an httpOnly cookie. FastAPI verifies the Better Auth JWT (JWKS) *(spec 018; real login needs Google OAuth keys)*
- [x] Account page: profile, allergens/diets, scan history, delete-everything *(spec 018)*
- [x] RLS policies on `scan_history`, `favorites` and `user_preferences`; tests prove user A can't read user B's rows
- [x] `GET/DELETE /me/history`, favorites, `PUT /me/preferences`; allergen/diet conflicts flagged on the product page

**⛳ MVP demo** at the end of week 8.

## M6: Voice + launch polish (weeks 9–10)

- [x] Voice: Web Speech STT → intent router (score, why, additives, allergens, alternatives) → browser `speechSynthesis`; "read this product aloud" *(spec 022; kokoro-js dropped: 86 MB model and a GPL-3.0 eSpeak NG phonemizer)*
- [x] Methodology page, `engine_version` changelog, About/attribution page, privacy page *(specs 018, 019)*
- [x] Deploy configs: web → Vercel; API → Render free (Dockerfile); DB → Supabase; weekly pipeline cron in GitHub Actions *(specs 020, 021; `docs/DEPLOY.md`. Going live needs the accounts)*
- [x] License check in CI (`pip-licenses`, `pnpm licenses`): fail on GPL/AGPL
