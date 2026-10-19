# 017: Add a missing product from a label photo

Status: implemented

When a barcode isn't found anywhere (LOOKUP-7, USDA-9), the user can photograph the label.
The browser reads the Nutrition Facts panel, the user checks and corrects every field, and
the product is saved and scored. The photo never leaves the device unless the user
explicitly opts in to sharing it with Open Food Facts.

Robotoff (Open Food Facts' extraction service) only works on photos already uploaded to Open
Food Facts, so text recognition runs in the browser with Tesseract.js (Apache-2.0). Like the
barcode decoder (SCAN-11), its worker, WASM core and English language data are served from
our own site, never a CDN.

## Reading the label (browser)

- **CONTRIB-1** The "not found" page offers "Add it from a label photo". The flow asks for a
  photo of the Nutrition Facts panel (camera or file), shrinks it to at most 1600 px on the
  long side, and reads the text with Tesseract.js loaded from `/tesseract/`.
- **CONTRIB-2** A parser reads the US Nutrition Facts panel: serving size in grams or ml,
  calories, total fat, saturated fat, sodium (mg), total carbohydrate, dietary fibre, total
  sugars and protein. Values are per serving, and are converted to per 100 g using the
  serving size. A field that can't be read stays empty. Nothing is guessed.
- **CONTRIB-3** The user sees every field in an editable form, pre-filled from the photo,
  with the product name, brand and optional ingredients. The four fields needed to score
  (energy, sugars, saturated fat, salt) are required. Nothing is saved until the user
  confirms.

## Saving (`POST /contributions`)

- **CONTRIB-4** The body has `gtin`, `name`, `brand?`, `ingredients_text?`, `kind` and
  `nutrition`. `kind` is what the user says the product is (`food`, `drink`, `cheese`, or
  `fat_oil_nut_seed`) and sets the Nutri-Score class through one category tag
  (`en:beverages`, `en:cheeses`, `en:fats`, or none). `nutrition` is per 100 g:
  `energy_kj`, `sugars_g`, `saturated_fat_g`, `salt_g`, `fat_g?`, `fiber_g?`, `proteins_g?`. The GTIN is validated per spec 001. Values must be numbers within
  physical limits: 0–3,800 kJ, grams 0–100, and saturated fat ≤ fat when both are given.
  Otherwise the response is `422` problem+json naming the field.
- **CONTRIB-5** A contribution is accepted only for a GTIN that has no product yet. If one
  exists, the response is `409`, so a contribution never overwrites source data.
- **CONTRIB-6** An accepted contribution creates the product
  (`source_by_field` = `contribution` for every field), stores the confirmed fields in
  `contributions` (`status = "accepted"`, no photo, no user id until accounts exist), scores
  it, and returns `201` with the product in the same shape as `GET /products/{gtin}`.
- **CONTRIB-7** The product page marks contributed products: "Added by a user from a label
  photo. Not yet checked."
- **CONTRIB-8** At most 20 contributions per client IP per hour (`429` after that), to limit
  abuse. The IP is not stored.

## Sharing with Open Food Facts (opt-in)

- **CONTRIB-9** If the server has Open Food Facts credentials (`OFF_USER`, `OFF_PASSWORD`),
  the form shows an unticked "Also add it to Open Food Facts (ODbL)" checkbox. Without them,
  the checkbox isn't shown.
- **CONTRIB-10** When ticked, the server sends the confirmed name, brand, ingredients and
  per-100 g nutrients to Open Food Facts' product write API with our User-Agent. Its
  outcome is stored on the contribution (`shared_with_off`). A failure there never fails
  the contribution. The photo is not uploaded in v1.
