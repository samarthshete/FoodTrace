# 019: Methodology and About pages

Status: implemented

Two public pages explain how the score works and where the data comes from. The
methodology page takes its numbers from the API, which reads the same `config/scoring.yaml`
as the engine, so the page can't drift from the scoring code.

## `GET /methodology`

- **METH-1** Returns `engine_version`, the component `weights`, the `bands`, the NOVA
  values, the additive `risk_penalty`, `evidence_weight` and `cap_total`, and the source
  URLs, all read from the scoring config. `Cache-Control: public, max-age=3600`.
- **METH-2** It also returns the `changelog`, one entry per `engine_version` with its
  change. The entries live in `config/scoring.yaml` under `changelog`, and must match the
  changelog table in spec 005 exactly (a test checks this). The newest version must equal
  `engine_version`.

## `/methodology` page

- **METH-3** It explains the score in plain words: `60·N + 30·A + 10·P`, with sections
  anchored `#nutrition`, `#additives` and `#processing` (the targets of the breakdown's
  component lines, ENGINE-9), plus the bands. Every number shown comes from
  `GET /methodology`.
- **METH-4** It explains missing data (rescaled score, confidence badge, "not scored"),
  estimates from the ingredient list (spec 014), and the golden gate result (spec 015). It
  links each rule's source.
- **METH-5** It lists the engine changelog, newest first. If the API is unreachable, the
  page says so instead of showing stale numbers.

## `/about` page and footer

- **METH-6** `/about` identifies the app as **FoodTrace**, uses
  **AI-Powered Grocery Intelligence Platform** as its tagline, says what the app is and
  isn't (educational, not medical advice), and
  credits every data source with its license: Open Food Facts (ODbL), USDA FoodData Central
  (public domain), openFDA (public domain), the FDA Substances Added to Food inventory (US
  government work), EFSA evaluations through the Open Food Facts taxonomy, and
  Nutri-Score. It links the source code (MIT).
- **METH-7** Every page's footer uses the **FoodTrace** name and **FT** initials, links
  Methodology, About and Privacy, and shows the Open Food Facts credit and
  "Educational information, not medical advice."
- **METH-8** `/methodology` and `/about` have no axe-detected WCAG 2.1 AA violations.
