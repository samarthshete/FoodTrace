# FoodTrace kickoff: starting the build in Claude Code

## 1. Open the project

```
cd /path/to/FoodTrace
claude
```

Claude Code reads `CLAUDE.md` automatically. Press **Shift+Tab** to switch to plan mode.

## 2. Paste this prompt

```
Read CLAUDE.md, docs/SPEC.md and docs/PLAN.md. Then plan M0 (repo scaffold)
and the first three M1 tasks. Before writing any import code, download the
OFF parquet and inspect its real schema with DuckDB. Don't assume column
names from the spec. Stop after M0 passes its "done when" check and show me
the results.
```

## 3. Things only you can do

- [ ] Download the **USDA Branded Foods** CSV from https://fdc.nal.usda.gov/download-datasets and unzip it into `data/usda/`
- [ ] Collect **~200 real US barcodes** (pantry, receipts, a grocery run), one per line, into `data/coverage_sample.txt`, for the week-2 coverage gate
- [ ] Decide the open questions in `docs/SPEC.md` §10 (repo license first)

The Open Food Facts dump (~4.2 GB) can be downloaded by Claude Code itself.
