# 003: Additives (A component)

Status: implemented

The additives component starts at 1.0 and loses a penalty for each additive with a known
risk. All weights are in `config/scoring.yaml` under `additives`.

## Reference data

Additive records come from the Open Food Facts additives taxonomy (ODbL):
https://static.openfoodfacts.org/data/taxonomies/additives.json

| Field | Taxonomy property | Mapping |
| --- | --- | --- |
| `risk_level` | `efsa_evaluation_overexposure_risk` | `en:high → 3`, `en:moderate → 2`, `en:no → 0`, absent → `null` (unrated) |
| `evidence_grade` | `efsa_evaluation` present? | EFSA evaluation with an overexposure assessment → `A`; EFSA evaluation without one → `B`; no evaluation → `C` |
| `source_url` | `efsa_evaluation_url` | else the OFF additive page `https://world.openfoodfacts.org/facets/additives/<code>` |

FDA status and EFSA OpenFoodTox ADI values are added in M1 (`pipeline/reference.py`).
Until then those columns are null.

## Requirements

- **ADD-1** The component value is `max(0, 1 − Σ penalty)`.
- **ADD-2** `penalty = additives.risk_penalty[risk_level] × additives.evidence_weight[evidence_grade]`.
- **ADD-3** An additive with `risk_level = null` (unrated) or not found in the reference table gives 0 penalty. It is listed in the breakdown with `points: 0` and marked `unrated: true`.
- **ADD-4** Each additive appears once, even if the product lists it twice.
- **ADD-5** If any additive has `risk_level = 3` and `evidence_grade = A`, the engine caps the total score at `additives.cap_total` (default 49, the top of "mediocre"). The cap shows up in the breakdown as rule `additives.cap`.
- **ADD-6** If the product's additive list is unknown (no ingredients text and no additives tags), the component is `unknown`, not 1.0. The engine handles this per ENGINE-5.
- **ADD-7** A product with a known, empty additive list scores 1.0.
- **ADD-8** Breakdown lines use rule id `additives.<code>` (e.g. `additives.e250`) and carry the additive's `source_url`.

## Copy

Additive copy follows hard rule 4: say "high estimated overexposure risk per EFSA" or
"limited evidence of X at typical intake". Never "toxic", "dangerous" or "unsafe".
