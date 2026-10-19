# 012: USDA FoodData Central

Status: implemented

USDA Branded Foods is a second source of label data for US products. It is used two ways:

- in the bulk import, to fill nutrients that Open Food Facts lacks;
- live, for barcodes that Open Food Facts doesn't have at all.

USDA has no NOVA group, Nutri-Score or parsed additive list. Those stay unknown here; spec 014
derives what it can from the ingredient list.

## Mapping (shared by bulk and live)

- **USDA-1** Nutrient amounts are per 100 g (or 100 ml), keyed by nutrient id:
  energy kJ `1062`, else kcal `1008` × 4.184; sugars `2000`; saturated fat `1258`; fat `1004`;
  sodium `1093` (mg), converted to salt as mg ÷ 1000 × 2.5; fibre `1079`; protein `1003`.
  An amount that can't be parsed, or is negative, is missing.
- **USDA-2** The USDA `branded_food_category` maps to Open Food Facts category tags through
  `config/usda_categories.yaml`. These tags drive the Nutri-Score class (NS-1): drinks,
  milks, cheeses, fats and oils, nut butters. Every USDA product also gets
  `usda:<category-slug>` as its most specific category, for alternatives (spec 009).
- **USDA-3** Non-food and out-of-scope categories (supplements, infant formula, alcohol,
  household items) listed under `exclude` in the same file are never imported or scored.
  A live lookup of one gives "not found".

## Bulk gap-fill

- **USDA-4** `pipeline/usda_bulk.py` reads the Branded Foods CSV zip in place, streaming each
  member without unpacking it. It keeps rows for GTINs that are in the Open Food Facts US
  extract, and skips discontinued products and other markets. A GTIN listed more than once
  keeps its latest `available_date`.
- **USDA-5** When an Open Food Facts product lacks a nutrient that USDA has, USDA's value is
  used, and `source_by_field["nutrition.<field>"] = "usda"`. Open Food Facts values are never
  replaced. A missing ingredient list is filled the same way (`source_by_field
  ["ingredients_text"] = "usda"`). Completeness is recomputed after the fill.
- **USDA-6** The fill runs before the scorable filter (OFF-5), so a product that only becomes
  scorable with USDA nutrients is imported. The import report says how many fields were filled.

## Live fallback

- **USDA-7** When Open Food Facts doesn't have a barcode (LOOKUP-7), the API searches
  FoodData Central (`/fdc/v1/foods/search`, `dataType=Branded`) with the 14-digit form of
  the GTIN, using `USDA_API_KEY` from the environment (default `DEMO_KEY`, which is free but
  rate-limited). A result counts only if its `gtinUpc` normalizes to the same GTIN-13.
- **USDA-8** A USDA hit is upserted like an OFF hit (LOOKUP-6): name from `description`,
  brand from `brandName`, else `brandOwner`, with ingredients, nutrients (USDA-1) and
  categories (USDA-2). `source_by_field` says `usda` for every field. The response
  attribution adds "Nutrition data from USDA FoodData Central".
- **USDA-9** Not in USDA either → `404` with `"next": "contribute"`, as before. USDA unreachable,
  rate-limited or erroring counts as not found for that request and is logged. It never
  turns a 404 into a 503.
- **USDA-10** USDA requests send our User-Agent and time out after `usda_timeout_s` (4 s).
