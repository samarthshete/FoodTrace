# 011: Bulk import from Open Food Facts

Status: implemented

Preloads US products so that scans are cache hits and alternatives (spec 009) have something
to draw on. The tool is Polars, plus Python's streaming CSV reader. The source is Open
Food Facts' own CSV export (~1.3 GB gzipped). An earlier draft read the Hugging Face Parquet
export remotely, but anonymous range requests are rate-limited there.

## Extract

- **OFF-1** `pipeline/off_bulk.py` downloads the export once to `data/off/` with our
  User-Agent, then streams it row by row and keeps only the needed columns in
  `data/off/us.parquet`. Both are reused until `--refresh`. A malformed row is skipped, not
  fatal.
- **OFF-2** Kept rows have `en:united-states` as one of their `countries_tags`, an exact tag
  match. Obsolete products aren't in the export.

## Mapping

- **OFF-3** Each row is reshaped into the live API's product format and mapped with the same
  `map_product` as live lookups (spec 006, LOOKUP-13). Empty nutrient cells are missing, not
  zero. The CSV can't tell "no additives" from "not analysed", so a row with neither an
  ingredient list nor additives has an unknown additive list (ADD-6). The export has no
  estimated fruit/vegetable share. Spec 014 estimates it from the ingredients instead.
- **OFF-4** The image URL is the export's `image_url` (the front image).
- **OFF-5** A row is loaded only if its code is a valid GTIN (spec 001), it has a name, and it
  has the four nutrients needed to score it (energy, sugars, saturated fat, salt). Products
  without them are still found by live lookup. If a code appears twice, the latest edit
  (`last_modified_t`) wins.

## Load

- **OFF-6** Rows are COPYed into a temporary staging table and merged into `products` in one
  transaction. An existing row is replaced only if the source changed the product after we
  last fetched it (`last_modified_t` > `fetched_at`). So a newer live lookup is never
  overwritten, and an unchanged product isn't rewritten. Live-only products are never
  deleted.
- **OFF-7** Each written product's additive links are replaced. Codes missing from the
  `additives` table get a stub row (spec 003, ADD-3).
- **OFF-8** Every written product, and every loaded product without a score for the current
  `engine_version`, is scored. Bulk scores are stored without breakdown lines to save space.
  The lines are added the first time the product is viewed, with the same result (ENGINE-4).
- **OFF-9** The load runs in a single transaction. If the database would exceed 450 MB, the
  load is rolled back with an error, and nothing changes.
- **OFF-10** At most `--max-products` (default 100,000) products are loaded, the most scanned
  first (`unique_scans_n`). That is about 3.6 KB each with scores and indexes, which fits
  the hosted 450 MB budget.
- **OFF-11** The run prints a report: products offered, written, kept, scored, and the
  database size against the budget. Running it twice in a row writes nothing the second time.
