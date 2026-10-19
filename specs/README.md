# Specs

This project uses spec-driven development. `docs/SPEC.md` is the product-level spec.
The files here are **feature specs**: small, testable, and the source of truth for
behaviour. Code and tests are derived from them, never the other way round.

## Workflow

1. **Write or change the spec first.** Add or edit requirements in a `specs/NNN-*.md` file.
   Set its status to `draft`.
2. **Review.** A human reads the spec. When the requirements are agreed, set the status
   to `approved`. Settle open questions in the spec, not in code.
3. **Tests.** Write a test for every requirement, tagged with its ID. Python:
   `@spec("GTIN-3")` (alias of `pytest.mark.spec`). Web (Vitest, Playwright): put the
   ID in the test title, `it("[SCAN-5] accepts ...")`. A test can cover several IDs.
4. **Code.** Implement until the tests pass. When everything is in, set the status to
   `implemented`.
5. **Change = spec change.** A behaviour change starts with a spec edit in the same PR.
   Scoring changes also bump `engine_version` in `config/scoring.yaml` and get a
   changelog line in `specs/005-engine.md`.

`api/tests/test_spec_traceability.py` enforces two things in CI:

- every requirement ID in an `approved` or `implemented` spec has at least one test;
- every test's `spec(...)` marker or `[ID]` title tag points at a requirement ID that exists.

## Requirement format

Each requirement sits on its own line and starts with a bold ID:

```
- **GTIN-3** UPC-A (12 digits) is zero-padded to GTIN-13.
```

IDs are stable. Never renumber. Retire a requirement by striking it out (`~~...~~`)
and noting why; its tests go with it.

## Index

| Spec | Area | Status |
| --- | --- | --- |
| [001-gtin](001-gtin.md) | Barcode normalization and validation | implemented |
| [002-nutriscore-2023](002-nutriscore-2023.md) | Nutri-Score 2023 port (N component input) | implemented |
| [003-additives](003-additives.md) | Additive penalty (A component) | implemented |
| [004-processing](004-processing.md) | NOVA processing (P component) | implemented |
| [005-engine](005-engine.md) | Score combination, breakdown contract, bands | implemented |
| [006-product-lookup](006-product-lookup.md) | `GET /products/{gtin}` and breakdown | implemented |
| [007-scanner](007-scanner.md) | Camera scanner and manual entry | implemented |
| [008-product-page](008-product-page.md) | Product page and PWA shell | implemented |
| [009-alternatives](009-alternatives.md) | Better-scored alternatives (API + strip) | implemented |
| [010-recalls](010-recalls.md) | openFDA recall banner | implemented |
| [011-bulk-import](011-bulk-import.md) | Bulk import of US products from the OFF export | implemented |
| [012-usda](012-usda.md) | USDA FoodData Central: bulk gap-fill and live fallback | implemented |
| [013-us-additive-status](013-us-additive-status.md) | US regulatory status of additives (FDA) | implemented |
| [014-ingredient-estimates](014-ingredient-estimates.md) | Fruit/veg share, NOVA and additives estimated from ingredients | implemented |
| [015-golden-gate](015-golden-gate.md) | Nutri-Score agreement with Open Food Facts (≥ 99%) | implemented |
| [016-search](016-search.md) | Search by product or brand name | implemented |
| [017-contributions](017-contributions.md) | Add a missing product from a label photo | implemented |
| [018-accounts](018-accounts.md) | Google sign-in, preferences, history, favorites, allergen warnings | implemented |
| [019-launch-pages](019-launch-pages.md) | Methodology and About pages, site footer | implemented |
| [020-scheduled-jobs](020-scheduled-jobs.md) | Daily recall sync and weekly data refresh (GitHub Actions) | implemented |
| [021-deploy](021-deploy.md) | Deployment: Docker API, Render, Vercel, Supabase | implemented |
| [022-voice](022-voice.md) | Ask about a product by voice or text; read aloud | implemented |
| [023-assistant](023-assistant.md) | Voice assistant tab: ask about any product, by condition | implemented |
| [024-explore](024-explore.md) | Explore the top foods per category | implemented |
| [025-response-cache](025-response-cache.md) | In-memory cache of public responses; stale on outage | implemented |
