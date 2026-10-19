# 010: Recall banner

Status: implemented

The product page shows a banner when an openFDA food enforcement (recall) record matches the
product (SPEC F9). openFDA is not a live alert feed, and our matching can't be certain, so the copy
always says a recall is *on record*, never that the product *is recalled*.

## Data

- **RECALL-1** `pipeline/recalls.py` downloads the openFDA bulk food enforcement file
  (`download.open.fda.gov/food/enforcement/…json.zip`, ~6 MB, listed in
  `api.fda.gov/download.json`). It does not page through the live API. It sends the same
  descriptive User-Agent as the OFF client.
- **RECALL-2** Records with `report_date` in the last `recalls.window_years` (3) years are
  upserted into a `recalls` table keyed by `recall_number`. Older records and records that
  dropped out of the file are deleted, so the table mirrors the window. The run time is stored
  as the data's `as_of`.
- **RECALL-3** At load time, every 12- or 13-digit run in `product_description`, `code_info` and
  `more_code_info` is extracted into a `codes` array, normalized to GTIN-13. Spaces and hyphens
  between digits are removed first, so `0 49000 02891 1` counts. Runs that fail the check digit
  are dropped.
- **RECALL-4** The sync is idempotent. Running it twice gives the same table. It runs daily
  from GitHub Actions once the hosted DB exists, and by hand until then.

## Matching

- **RECALL-5** **Code match:** the product's GTIN-13 is in a record's `codes`.
- **RECALL-6** **Brand and name match:** the product's brand appears as whole words in the
  record's `product_description` or `recalling_firm`, and so do its name words. Text is
  lowercased, accents and punctuation are stripped, and only the first brand of a
  comma-separated list is used. "Name words" are the product name's words of 3 or more letters
  that are not the brand and not stop words. At least 2 must appear, or 1 if the name has only 1.
- **RECALL-7** A brand shorter than 3 letters, or a product with no brand or no name, can only
  match by code. Generic store brands (`recalls.generic_brands`, e.g. "great value",
  "kirkland signature") never match on brand alone. They need a code match.

## `GET /products/{gtin}/recalls`

- **RECALL-8** The product is resolved with the spec 006 lookup path, so the errors are the
  same. The response has `gtin`, `recalls`, `as_of` (the last sync time, or `null` if the table
  has never been loaded) and `attribution: "Recall data from openFDA (FDA)"`.
- **RECALL-9** Each recall has `recall_number`, `match` (`"code"` or `"brand_name"`),
  `classification`, `status`, `reason_for_recall`, `recall_initiation_date` (ISO date),
  `product_description` and `url`. The `url` is the openFDA query for that `recall_number`.
- **RECALL-10** Code matches come first, then the rest by `recall_initiation_date`, newest first.
  At most 3 are returned.
- **RECALL-11** The response carries `Cache-Control: public, max-age=3600`. Recall data changes
  daily, so this endpoint has no ETag and is separate from the product's cached response.

## Product page

- **RECALL-12** If `recalls` is not empty, a banner sits above the score. The heading is
  "A related FDA recall is on record", or "An FDA recall on record lists this barcode" for a
  code match. Below it are the newest record's reason (as FDA wrote it), its start date, and a
  "View the FDA record" link. If there are more records, it says "and N more".
- **RECALL-13** The copy never says the product "is recalled", "unsafe" or "dangerous". A
  brand-and-name match adds "This may be a different product from the same brand." The banner
  shows "FDA data as of {date}".
- **RECALL-14** No records, a `null` `as_of`, or a failed request means no banner. The product
  page still renders.
- **RECALL-15** The banner is announced to screen readers (`role="status"`) and does not rely
  on colour alone.
