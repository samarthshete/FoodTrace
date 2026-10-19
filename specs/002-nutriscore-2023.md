# 002: Nutri-Score 2023

Status: implemented

A clean-room port of the 2023 Nutri-Score algorithm. It is written from the Scientific
Committee reports, not from Open Food Facts code (which is AGPL). Every threshold lives
in `config/scoring.yaml` under `nutriscore`.

Sources:
- General foods, cheese, and fats/oils/nuts/seeds: *Update report from the Scientific Committee of the Nutri-Score*, 2022, appendix tables 1.1–2.4.
  https://mpc.gouvernement.lu/dam-assets/le-minist%C3%A8re/consodur/2022-main-algorithm-report-update-final.pdf
- Beverages: *Update of the Nutri-Score algorithm for beverages*, second update report, 2023, appendix "Points allocation" and "Final Nutri-Score thresholds".
  https://edepot.wur.nl/629571

## Inputs (per 100 g, or per 100 ml for beverages)

`energy_kj`, `sugars_g`, `saturated_fat_g`, `fat_g` (fats class only), `salt_g`,
`fiber_g`, `proteins_g`, `fvl_percent` (fruit, vegetables, legumes),
`has_non_nutritive_sweeteners` (beverages), `nutriscore_class`, `is_red_meat`.

## Requirements

### Class

- **NS-1** Each product gets one class: `water`, `beverage`, `cheese`, `fats_oils_nuts_seeds`, or `general`. It is decided from Open Food Facts category tags using the ordered lists in `config/scoring.yaml` (`nutriscore.classes`). The first match wins, in that order. No match means `general`.
- **NS-2** `is_red_meat` is true when any category tag is in `nutriscore.red_meat_tags`.

### Required inputs

- **NS-3** `energy_kj`, `sugars_g`, `saturated_fat_g` and `salt_g` are required for every class except `water`. If one is missing, the result is `not_computable` and lists the missing fields. For `fats_oils_nuts_seeds`, `fat_g` is also required.
- **NS-4** A missing `fiber_g`, `proteins_g` or `fvl_percent` scores 0 points for that component and is reported in `missing`. These fields are never guessed.

### Unfavourable points (A)

- **NS-5** General and cheese: energy 0–10 (each point above 335 kJ, step 335), sugars 0–15, saturated fat 0–10, salt 0–20. Thresholds as in the 2022 report, appendix 1.1.
- **NS-6** Fats/oils/nuts/seeds: energy is replaced by *energy from saturates* = `saturated_fat_g × 37` kJ, 0–10 (step 120). Saturated fat is replaced by the ratio `saturated_fat_g / fat_g × 100`, 0–10 (`<10 → 0` … `≥64 → 10`). If `fat_g` is 0, the ratio is 0. Sugars and salt as in general.
- **NS-7** Beverages: energy 0–10 (`≤30 → 0`, `≤90 → 1`, `≤150 → 2`, `≤210 → 3`, then 30 kJ per point to `>390 → 10`), sugars 0–10 (`≤0.5 → 0`, `≤2 → 1`, `≤3.5 → 2`, `≤5 → 3`, then 1 g per point to `>11 → 10`). Saturated fat and salt as in general. Non-nutritive sweeteners present: 4 points.
- **NS-8** A threshold `t` gives its points when the value is strictly greater than `t`, except the fats saturates ratio, which uses `≥` on the lower bound of each band (`<10 → 0`, `<16 → 1`, …).

### Favourable points (C)

- **NS-9** General, cheese, fats: protein 0–7 (`>2.4, >4.8, >7.2, >9.6, >12, >14, >17`), fibre 0–5 (`>3.0, >4.1, >5.2, >6.3, >7.4`), fruit/veg/legumes 0, 1, 2 or 5 (`>40 → 1`, `>60 → 2`, `>80 → 5`).
- **NS-10** Beverages: protein 0–7 (`>1.2` then +0.3 g per point to `>3.0 → 7`), fibre as in general, fruit/veg/legumes 0, 2, 4 or 6 (`>40 → 2`, `>60 → 4`, `>80 → 6`).
- **NS-11** Red meat (general class only): protein points are capped at 2.

### Final score

- **NS-12** General: if A ≥ 11, protein points are **not** counted (score = A − fibre − fvl). Otherwise score = A − C.
- **NS-13** Cheese: protein is always counted (score = A − C).
- **NS-14** Fats/oils/nuts/seeds: if A ≥ 7, protein is not counted. Otherwise score = A − C.
- **NS-15** Beverages: score = A − C. Protein is always counted.
- **NS-16** Water: grade A, no points computed.

### Grade

- **NS-17** General and cheese: A ≤ 0, B 1–2, C 3–10, D 11–18, E ≥ 19.
- **NS-18** Fats/oils/nuts/seeds: A ≤ −6, B −5–2, C 3–10, D 11–18, E ≥ 19.
- **NS-19** Beverages: B ≤ 2, C 3–6, D 7–9, E ≥ 10. Only `water` can be A.

### Output

- **NS-20** The result lists each component with its input value, points, and the rule id `nutriscore.<class>.<component>` so the engine can copy it into the breakdown.
- **NS-21** The result includes `score`, `grade`, `class`, `min_score`, `max_score` (the theoretical range for the class, used by the engine to normalize) and `missing`.
- **NS-22** In the fats/oils/nuts/seeds class, olive, rapeseed (canola) and walnut oils (`nutriscore.fvl_oil_tags`) count as 100% fruit, vegetables and legumes (2023 update). The fvl line notes this.

## Golden gate

Our grade must match Open Food Facts' 2023 grade on ≥ 99% of a sample of ≥ 2,000
products that OFF scored with the 2023 algorithm and that have full nutriments.
Mismatches are written to `reports/golden_mismatches.csv`. This runs in M2 once
sample data is available. It is not a unit test, so it has no requirement ID.

## Known gaps (v0.1)

- Class detection uses category tags only. OFF also uses ingredient rules (e.g. the
  80% milk rule for milk drinks). Expect most golden-set mismatches here.
- Coffee, cocoa and chicory powders should be scored "as prepared". We score them as sold.
