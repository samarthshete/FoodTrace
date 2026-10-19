# 024: Explore the top foods per category

Status: implemented

A browsable "Explore" view: for each everyday category, the best-scored products, with their
score, band, Nutri-Score grade and NOVA group. Database only: it never calls a live source.

## Categories

- **EXPLORE-1** Ten fixed groups, each a set of Open Food Facts `primary_category` tags, in this
  order: breakfast (breakfast cereals, extruded cereals, mueslis, rolled oats),
  yogurts (yogurts, Greek-style yogurts), breads (breads, wheat breads, bagel breads,
  hamburger buns), snacks (potato crisps, corn chips, salted snacks, pretzel, crackers),
  bars (protein bars, cereal bars, bars), sweets (biscuits, cakes, candies,
  chocolate candies), drinks (sweetened beverages, beverages, milks, plant-based beverages,
  protein shakes), cheese (cheeses), meals (pastas, meals, pizzas, soups, canned soups, frozen
  foods) and spreads (peanut butters, honeys, canned common beans, eggs). Each has an `id`, a
  `label` and a one-sentence `blurb`.

## `GET /explore`

- **EXPLORE-2** Returns `{engine_version, categories: [{id, label, blurb, products}]}` with every
  group, in order, each with up to `per_category` products (default 6, clamped to 1–24). One
  database query serves the whole response. `Cache-Control: public, max-age=600`.
- **EXPLORE-3** A product is listed only if it has a score for the current `engine_version` with
  a total (not "not scored") and a non-empty name. Order within a group: products with an image
  first, then score (highest first), then completeness (highest first), then GTIN.
- **EXPLORE-4** Each product is `{gtin, name, brand, image_url, total, band, nutriscore_grade,
  nova_group}`. `band` is the stored band (`{id, label}`), as in search; `nutriscore_grade` is
  the stored Nutri-Score grade (`a`–`e`), or null when the score has none.

## `GET /explore/{id}`

- **EXPLORE-5** Returns `{id, label, blurb, products}` for one group with up to `limit` products
  (default 24, clamped to 1–60), ordered and filtered as in EXPLORE-3. An unknown id is a 404
  problem response. `Cache-Control: public, max-age=600`.

## Web (the app redesign)

- **EXPLORE-6** `/explore` lists every group with its top 4 products, and `/explore/{id}` shows up to
  48. Each product card shows its rank, score (with "out of 100" for screen readers), band,
  Nutri-Score grade and NOVA group when known, and links to its product page. Categories are a
  sidebar on wide screens and scrolling chips on phones; the current one has `aria-current`.
  When the API fails the page says top foods are unavailable instead of erroring.
- **EXPLORE-7** The app has four tabs, Explore, Scan, Lookup and Assistant: in the header on wide
  screens and a bottom tab bar on phones, with `aria-current="page"` on the active tab. Scan
  holds the camera and barcode typing; Lookup holds name search and barcode typing.
- **EXPLORE-8** The landing page (`/`) has a hero, a quick lookup (name search and barcode
  typing), "how it works", a preview of the top foods in three categories, a link to the
  assistant, and the principles. It stays white, with one accent colour (emerald).
