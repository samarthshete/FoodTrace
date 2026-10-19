# 001: GTIN normalization

Status: implemented

Every barcode is keyed as GTIN-13. Off-by-format barcodes are the main cause of false
"not found" results, so all input goes through one function before any lookup.

## Requirements

- **GTIN-1** Input may contain spaces and hyphens; they are stripped. Any other non-digit character makes the input invalid.
- **GTIN-2** Accepted lengths after stripping: 8 (EAN-8), 12 (UPC-A), 13 (EAN-13), 14 (GTIN-14). Any other length is invalid.
- **GTIN-3** EAN-8 and UPC-A are left-padded with zeros to 13 digits.
- **GTIN-4** GTIN-14 with a leading `0` is reduced to 13 digits. GTIN-14 with any other leading digit (a case/logistics indicator) is invalid for product lookup.
- **GTIN-5** The GS1 mod-10 check digit is validated on the original digits. A wrong check digit is invalid.
- **GTIN-6** UPC-E (6–8 digit zero-suppressed) is **not** expanded in v1. An 8-digit input is always treated as EAN-8.
- **GTIN-7** Normalization returns the canonical GTIN-13 string. Invalid input raises `InvalidGTIN` with a human-readable reason.
- **GTIN-8** `lookup_forms(gtin13)` returns the codes to try against Open Food Facts: the GTIN-13, plus the 12-digit form when the GTIN-13 starts with `0`. The GTIN-13 comes first.
- **GTIN-9** Normalization is idempotent: normalizing a GTIN-13 output returns it unchanged.

## Examples

| Input | Result |
| --- | --- |
| `036000291452` (UPC-A) | `0036000291452` |
| `0036000291452` | `0036000291452` |
| `036000291453` | invalid: check digit |
| `96385074` (EAN-8) | `0000096385074` |
| `00036000291452` (GTIN-14) | `0036000291452` |
| `10036000291459` (GTIN-14, indicator 1) | invalid: logistics code |
| `0 36000 29145 2` | `0036000291452` |
