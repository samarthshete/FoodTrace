# 013: US regulatory status of additives

Status: implemented

Each additive shows its US status as a plain fact, from FDA's "Substances Added to Food"
inventory (formerly EAFUS). That inventory is a US government work. The status is display
only. It doesn't change any score, so `engine_version` is unchanged.

EFSA's OpenFoodTox is **not** imported: it is licensed CC BY-ND 4.0, which forbids
derivatives. EFSA intake values (ADI) keep coming from the Open Food Facts additives taxonomy
(ODbL, already credited), and each additive links to its EFSA opinion.

## Data

- **FDA-1** `pipeline/reference.py` downloads the inventory export
  (`hfpappexternal.fda.gov/scripts/fdcc/cfc/XMLService.cfm?method=downloadxls&set=FoodSubstances`,
  a CSV despite the name) to `data/reference/fda_substances.csv` once, with our User-Agent,
  and reuses it until `--refresh`.
- **FDA-2** Each substance gets one status from the CFR parts it is listed under, highest
  first:
  `prohibited` (Part 189), `delisted` (a colour whose name ends in "DELISTED"),
  `food_additive` (Parts 172, 173 or 180), `color_additive` (Parts 73 or 74),
  `gras` (Parts 182, 184 or 186), `prior_sanctioned` (Part 181), `gras_flavor` (a FEMA GRAS
  number and no CFR listing). Indirect-only listings (Parts 175–178) give no status.
  `fda_cfr_ref` is the first CFR section for that status, e.g. `172.170`.
- **FDA-3** Additives are matched to FDA substances by name: the taxonomy's English name
  without its E-number prefix ("E250 - Sodium nitrite" → "sodium nitrite") against FDA's
  substance name and its listed other names. Names are compared lowercased, with HTML,
  punctuation and extra spaces removed. Only exact matches count. An additive with no match
  has no US status.
- **FDA-4** The run reports how many additives got a US status.
- **FDA-7** If the export can't be downloaded, or what comes back isn't the inventory (an error
  or block page), the bad response is not cached. The additives load still completes with a
  warning, and stored US statuses are left as they were. An FDA outage never fails a data run
  or CI.

## API and page

- **FDA-5** `GET /products/{gtin}` includes `additives`: one entry per additive on the
  product, with `code`, `name`, `us_status` and `fda_cfr_ref` (null when unknown).
- **FDA-6** On the product page, each additive line adds its US status in words below the
  EFSA rating:
  - `food_additive`: "US: approved food additive (21 CFR 172.170)"
  - `color_additive`: "US: approved color additive (21 CFR 74.303)"
  - `gras`: "US: generally recognized as safe, GRAS (21 CFR 184.1033)"
  - `prior_sanctioned`: "US: prior-sanctioned (21 CFR 181.33)"
  - `gras_flavor`: "US: flavoring, GRAS per FEMA"
  - `delisted`: "US: color listing ended (delisted)"
  - `prohibited`: "US: prohibited in food (21 CFR 189.120)"

  No status → no line. The CFR reference links to the eCFR section.
