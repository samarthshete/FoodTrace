# 004: Processing (P component)

Status: implemented

## Requirements

- **PROC-1** NOVA group maps to a component value via `processing.nova_values` in `config/scoring.yaml`: 1 → 1.0, 2 → 0.67, 3 → 0.33, 4 → 0.0.
- **PROC-2** A missing NOVA group is estimated from the ingredient list when there is one (spec 014, EST-3) and flagged `estimated`. Otherwise the component is `unknown`, and the engine handles it per ENGINE-5.
- **PROC-3** A NOVA value outside 1–4 is treated as missing.
- **PROC-4** The breakdown line uses rule id `processing.nova` with the NOVA group as `input_value` and the source `https://world.openfoodfacts.org/nova`.
- **PROC-5** Organic status gives no points. It is shown as an info badge only (SPEC §10 default).

## Later (M2)

Deriving NOVA for USDA-only products from ingredient markers. That will be a separate
requirement with its own heuristic doc and `estimated: true` on the breakdown line.
