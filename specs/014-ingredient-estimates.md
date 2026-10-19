# 014: Estimates from the ingredient list

Status: implemented

Some sources leave scoring inputs blank. The OFF CSV export has no fruit/vegetable share, and
USDA has no NOVA group and no additive list. When the ingredient list is known, the engine
estimates what it can from it. Every estimate is flagged `estimated` and says so on the page.
Estimates are conservative: they use only what the label states, never more. An input
that can't be estimated stays missing, which lowers confidence (ENGINE-5, ENGINE-10).

This changes engine output, so `engine_version` becomes **0.2.0**. Products are re-scored
under the new version, and 0.1.0 rows are kept (LOOKUP-9).

## Parsing

- **EST-1** The ingredient text is split into ingredients at top-level commas and semicolons,
  not inside brackets. A leading "Ingredients:" is dropped. Each ingredient keeps a stated
  percentage if it has one ("tomatoes (45%)", "45% tomatoes"). Text is lowercased, and
  punctuation at the ends is removed. Sub-ingredients in brackets count as part of their
  parent, e.g. "chocolate (sugar, cocoa)".

## Fruit, vegetables and legumes

- **EST-2** If `fvl_percent` is missing, it is estimated from ingredients whose name matches
  `estimates.fvl_words` (fruits, vegetables, legumes; Nutri-Score 2023 excludes potatoes and
  nuts). The estimate is the sum of their stated percentages, capped at 100. One that has no
  percentage counts as 0, so the estimate is a lower bound. A product whose only ingredient is
  a fruit, vegetable or legume is 100%. With no parseable ingredients, the value stays
  missing.

## Processing (NOVA)

- **EST-3** If the NOVA group is missing, it is derived from the ingredients, using marker
  lists in `config/scoring.yaml` (`estimates.nova`), following the NOVA definitions:
  - **4** if any ingredient contains an ultra-processing marker (e.g. high-fructose corn
    syrup, maltodextrin, hydrogenated oil, modified starch, protein isolate, flavoring,
    artificial color, emulsifier, non-nutritive sweetener);
  - else **2** if every ingredient is a culinary ingredient (sugar, salt, oil, butter,
    vinegar, honey, syrup), e.g. "olive oil, salt";
  - else **3** if there are two or more ingredients and at least one is culinary;
  - else **1**.
  Measured on 20,000 US Open Food Facts products that have a NOVA group: the estimate agrees
  91% of the time. It rarely calls an unprocessed food ultra-processed (23 of 1,959).
- **EST-4** A derived NOVA group is flagged `estimated`. Its note says "estimated from the
  ingredient list" and names the marker that decided group 4.

## Additives (USDA products)

- **EST-5** A USDA product (spec 012) with an ingredient list gets its additives by matching
  the `additives` table's names ("E250 - Sodium nitrite" → "sodium nitrite") and E-numbers
  ("e250") as whole words in the ingredient text. The list then counts as known, and
  `source_by_field["additives"] = "derived"`.

## Output

- **EST-6** `ProductFacts` carries `ingredients_text`. The same facts and `engine_version` still
  always give the same output (ENGINE-4).
- **EST-7** Estimated inputs are named in the explanation ("Estimated from the ingredient
  list: …") and marked "Estimated" on their breakdown line. They don't count towards
  `confidence`.
