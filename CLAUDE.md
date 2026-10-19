# FoodTrace

**AI-Powered Grocery Intelligence Platform**

A mobile-first PWA: scan a US grocery barcode and get a 0–100 health score in which every point traces back to a rule and a cited source. It runs on open data and open-source software, with **$0/month infrastructure**.

Full spec: `docs/SPEC.md`. Build order and acceptance criteria: `docs/PLAN.md`. Read both before starting a milestone.

## Spec-driven development (how every change is made)

Feature behaviour is defined in `specs/NNN-*.md` as numbered requirements (`**GTIN-3**`). Workflow is in `specs/README.md`:

1. Write or edit the spec first. New specs start as `Status: draft` and need human review before code.
2. Tag every test with the requirement IDs it covers: `@spec("GTIN-3")` in Python, `[GTIN-3]` in web test titles.
3. Implement until the tests pass, then set the spec to `implemented`.

`api/tests/test_spec_traceability.py` fails CI if an approved or implemented requirement has no test, or a test cites an unknown ID. Never renumber IDs. Retire them with `~~strikethrough~~`.

## Hard rules (never break these)

1. **Zero cost.** No paid APIs, no usage-billed services, no API keys that can incur charges. Don't add a dependency on any hosted service without asking first (approved: Groq's free tier for the assistant, spec 023). Heavy compute goes in the browser or the offline pipeline, never the server.
2. **No LLM in the scoring path.** Scoring is a pure, deterministic Python module. The same inputs and `engine_version` always give the same score. Product explanations are rendered from templates over the score breakdown.
3. **Licenses.** Don't copy code from AGPL/GPL projects (e.g. the Open Food Facts server, Piper TTS). Port logic from their docs and test against their outputs instead. Run the license check before adding a dependency. Open Food Facts data is ODbL: attribute it everywhere it's shown.
4. **Health language.** Never write "toxic", "dangerous", or "unsafe" in user-facing copy. Say "limited evidence of X at typical intake", state regulatory status as fact, and show the "educational, not medical advice" footer.
5. **Missing data lowers confidence, not the score.** Never guess a nutrient value. Estimated fields are flagged. If required inputs are missing, the product is "not scored".
6. **Privacy.** Scan history is health-adjacent. Collect the minimum, keep it deletable in one call, and enforce row-level security per user. No third-party analytics.

## Stack

| Layer | Choice |
| --- | --- |
| Offline pipeline | Python 3.12 + Polars (streams the OFF CSV export and the USDA zip; never loads them whole) |
| API | FastAPI + SQLAlchemy 2 + Alembic, async (`asyncpg`) |
| DB | PostgreSQL 16 (`pg_trgm`, full-text search, JSONB, RLS). Local: Docker. Hosted: Supabase free tier (500 MB cap: keep the DB ≤ 450 MB) |
| Web | Next.js (App Router) + TypeScript + Tailwind, installable PWA |
| Barcode | `barcode-detector` (BarcodeDetector polyfill on ZXing-C++ WASM). Do NOT use `html5-qrcode` (unmaintained) |
| OCR | Robotoff nutrition extraction API first, Tesseract.js fallback in the browser |
| Auth | Better Auth |
| Voice | Assistant mic: Groq Whisper (`whisper-large-v3-turbo`) via `/api/assistant/transcribe` when `GROQ_API_KEY` is set, else Web Speech API `SpeechRecognition` (opt-in, after a notice); `speechSynthesis` for answers. Not `kokoro-js`: its phonemizer bundles GPL-3.0 eSpeak NG |
| Assistant | Groq free tier (`openai/gpt-oss-20b`) only turns a question into fixed fields; answers are templates over label data. Optional: keyword rules without `GROQ_API_KEY` |
| Python tooling | `uv`, `pytest`, `ruff`, `mypy` |
| JS tooling | `pnpm`, `eslint`, `vitest`, Playwright for e2e |
| CI | GitHub Actions (tests + lint on PR; weekly data refresh cron) |

## Repo layout

```
pipeline/        offline data: reference.py (additives), recalls.py (openFDA), off_bulk.py + load.py (bulk OFF import), usda_bulk.py (USDA gap-fill)
specs/           feature specs with requirement IDs (the source of truth for behaviour)
api/app/         FastAPI app: main.py, auth.py, routers/ (products, search, contributions, me), services/ (gtin, off_client, off_mapping, lookup, alternatives, recalls), db/
api/app/scoring/ engine.py, nutriscore_2023.py, additives.py, processing.py, explain.py, config.py
api/migrations/  Alembic migrations
api/tests/       unit/, integration/ (Docker Postgres, OFF mocked with respx), pipeline/, golden/ (3,000-product ODbL sample; CI enforces >= 99%)
web/             Next.js PWA
config/scoring.yaml   weights and thresholds; bump engine_version on any change
data/            raw dumps (gitignored, never committed)
docs/            SPEC.md, PLAN.md, DEPLOYMENT_GUIDE.md (complete free-tier deploy)
```

## Commands

```
cp .env.example .env                          # then set OFF_CONTACT
uv run pre-commit install --install-hooks      # once: lint, format, secrets and commit-message checks before each commit
docker compose up -d db                       # local Postgres 16 (also creates ofs_test for tests)
uv run alembic upgrade head                   # migrations
uv run python -m pipeline.reference           # load the additives table: OFF taxonomy + FDA US status (--refresh re-downloads)
uv run python -m pipeline.recalls             # sync openFDA recalls (last 3 years, ~6 MB download)
uv run python -m pipeline.off_bulk            # bulk-load US products from the OFF export (~1.3 GB download, cached in data/off/)
                                              # with data/usda/branded.zip present (FDC Branded Foods CSV), USDA fills nutrient gaps
uv run pytest                                 # unit + integration + spec traceability
uv run pytest --cov                           # same, with coverage (fails under 85%)
uv run python -m pipeline.golden              # golden gate on the full US extract (>= 99% Nutri-Score match with OFF)
uv run ruff check . && uv run ruff format --check . && uv run mypy api pipeline   # lint and types
uv run fastapi dev api/app/main.py            # API on :8000
scripts/warm-cache.sh                         # after starting the API: pre-load demo products and Explore (spec 025)
cp web/.env.example web/.env.local            # accounts: Better Auth secret, DB URL, Google OAuth keys
cd web && corepack pnpm@10.18.3 install       # web deps (also copies the ZXing .wasm into public/)
cd web && pnpm dev                            # PWA on :3000; reads API_URL (default http://localhost:8000)
cd web && pnpm test && pnpm lint && pnpm typecheck   # Vitest, ESLint, tsc (with Next route typegen)
cd web && pnpm e2e                            # Playwright: own API on :8001 + prod build on :3100, DB ofs_test
```

Update this section as soon as a command changes.

## Conventions

- **The barcode key is GTIN-13.** Normalize every input (UPC-A, EAN-8, EAN-13), zero-padded, and validate the mod-10 check digit before any lookup. Off-by-format barcodes are the #1 cause of false "not found".
- **The scoring breakdown is the contract.** The engine returns `[{rule_id, component, points, input_value, source_url, estimated}]` (specs/005). The UI and the explanations read only from this list.
- **Scores are versioned.** The `scores` primary key is `(gtin, engine_version)`. Never update a score row in place across versions.
- **Track sources per field.** `products.source_by_field` records whether each field came from `off` or `usda`. The merge keeps the more complete value per field.
- **Be a good Open Food Facts citizen.** Cache first, send a descriptive User-Agent (`FoodTrace/0.1 (contact email)`), back off on 429s, and use the bulk dump for anything predictable.
- **Tests come with the code.** Every scoring rule gets a unit test. Any change to the lookup flow gets an integration test against the Docker DB.
- **Commit and PR titles follow Conventional Commits** (`feat(scope): …`, `fix: …`). A commit-msg hook and the PR-title check enforce it; release-please builds CHANGELOG.md from them. PRs are squash-merged, so the PR title becomes the commit on `main`.
- Dependabot opens weekly grouped update PRs; CodeQL scans every PR. Treat their PRs like any other: CI must pass.
- Keep functions small and typed. No new top-level dependency without a one-line reason in the PR description.

## Gotchas

- `fastapi[standard]` pulls in an OpenTelemetry exporter. Don't use it: depend on `fastapi`, `fastapi-cli` and `uvicorn[standard]` instead (privacy rule 6).
- This is Next.js 16: read `web/node_modules/next/dist/docs/` before writing Next code. With Cache Components on, route `params` are request-time data and must be read inside `<Suspense>`.
- Next 16 keeps the previous route mounted but hidden after navigation. In Playwright, scope text queries (e.g. to `footer`) or they match the hidden page too.
- Tesseract.js (label photos) also defaults to a CDN. `src/lib/ocr.ts` points it at `/tesseract/`, filled by `scripts/copy-ocr-assets.mjs` at install; keep it that way (spec 017).
- `barcode-detector` fetches its WASM from jsDelivr by default. `src/lib/detector.ts` overrides that to `/zxing/`; keep it that way (spec 007, SCAN-11).
- Better Auth's tables (`user`, `session`, `account`, `verification`, `jwks`) are created by Alembic migration 0006, not Better Auth's migrator; keep them in step when upgrading better-auth.
- `/me` routes must run inside `as_user()` (routers/me.py): it switches to the `ofs_app` role, which has no BYPASSRLS, and sets `app.user_id`. A query outside it runs as the owner and skips row-level security.
- EFSA OpenFoodTox is CC BY-ND 4.0 (no derivatives): don't import it. ADIs come from the OFF taxonomy (ODbL).
- FDA's "Substances Added to Food" export is a CSV despite its `downloadxls` URL, with a preamble before the header. Cells look like `=T("172.170")`.
- OFF taxonomy properties are keyed by language (`{"en": "en:high"}`). Unwrap them; don't expect plain strings.
- The OFF CSV export is ~1.3 GB gzipped (~4M products). `pipeline/off_bulk.py` streams it and keeps US rows only. Don't read Hugging Face's ~8 GB Parquet remotely: anonymous range requests get rate-limited (429).
- The hosted DB budget is 450 MB, about 100,000 products with scores. Bulk scores are stored without breakdown lines; the lookup fills them in on first view.
- In OFF, US products may be stored with 12- or 13-digit codes. Look up both forms.
- USDA Branded Foods has no NOVA group, no Nutri-Score, and no parsed additives. Derive them from its ingredient text and nutrient rows.
- USDA stores barcodes as 14-digit GTINs: search FoodData Central with `gtin.zfill(14)`; the 12- or 13-digit form finds nothing. `DEMO_KEY` allows ~10 requests an hour; set `USDA_API_KEY` (free at api.data.gov) for real use.
- USDA spells categories inconsistently (`A  B`, `A - B`, `A – B`). `usda_mapping.category_key` normalizes them; key `config/usda_categories.yaml` the same way.
- The API caches public GET responses in memory (spec 025) and serves the last good copy when the database is unreachable. Responses carry `X-Cache: hit|miss|stale`. Integration tests turn it off via `app.state.response_cache = None`.
- Supabase Free can pause low-activity projects and has no automatic backups. Daily database work reduces idle time but does not guarantee the project stays active; monitor pause notices and follow `docs/DEPLOYMENT_GUIDE.md`.
- `.github/workflows/data-refresh.yml` does nothing until the repo has a `DATABASE_URL` secret (asyncpg form). Optional: `OFF_CONTACT` and `USDA_BRANDED_ZIP_URL` repository variables.
- Any scoring change must keep the golden gate at >= 99% (`api/tests/golden`). Run `pipeline.golden` on the full extract and read `reports/golden_mismatches.csv` before changing class tags or thresholds.
- Nutri-Score has separate rules for general foods, beverages, cheese, and fats/oils/nuts/seeds. Always pass the category.
