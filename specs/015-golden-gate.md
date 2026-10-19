# 015: Golden gate (Nutri-Score agreement with Open Food Facts)

Status: implemented

Our Nutri-Score 2023 port is checked against Open Food Facts' own grades on real US products
(SPEC §2: ≥ 99% on ≥ 2,000 products). This catches porting mistakes, like the two found
when the gate was first run:

- generic waters were in the water class (OFF scores only spring and mineral waters as water);
- olive, rapeseed and walnut oils didn't count as 100% fruit/vegetables/legumes (NS-22).

## Requirements

- **GOLD-1** A product is in the golden set if OFF gives it a grade A–E and it has a full
  nutrition panel: energy, sugars, saturated fat, salt, fibre and protein.
- **GOLD-2** Each product is mapped exactly as the import maps it (spec 011), estimates
  included (spec 014), and graded by `nutriscore_2023.compute`.
- **GOLD-3** `uv run python -m pipeline.golden` grades the full US extract, prints the
  match rate per class, and writes every mismatch to `reports/golden_mismatches.csv`.
- **GOLD-4** It exits non-zero if fewer than 2,000 products are graded or under 99% match.
- **GOLD-5** CI runs the gate on a committed sample of 3,000 US products
  (`api/tests/golden/off_us_sample.parquet`, Open Food Facts data under ODbL). The match must
  be ≥ 99%. Any change to the scoring config or engine that breaks this fails the build.

Results when first run (engine 0.3.0, 2026-10-12): 41,750 products, **99.27%** match. Water
42/42, cheese 1,185/1,186, drinks 1,954/1,968, general 36,520/36,708, fats/oils/nuts/seeds
1,743/1,846. Most remaining mismatches are salted or roasted nuts, which OFF scores as
general foods for reasons not yet understood.
