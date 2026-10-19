"""Barcode normalization to GTIN-13 (specs/001-gtin.md)."""

import re

_SEPARATORS = re.compile(r"[\s-]+")


class InvalidGTIN(ValueError):
    """The input can't be used as a product barcode."""


def check_digit_ok(digits: str) -> bool:
    """GS1 mod-10: weights 3,1,3,... from the right, excluding the check digit."""
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def normalize(raw: str) -> str:
    """Return the canonical GTIN-13 for a barcode, or raise InvalidGTIN."""
    digits = _SEPARATORS.sub("", raw)
    if not digits.isdigit():
        raise InvalidGTIN("A barcode may only contain digits.")
    if len(digits) not in (8, 12, 13, 14):
        raise InvalidGTIN(f"A barcode has 8, 12, 13 or 14 digits, not {len(digits)}.")
    if len(digits) == 14 and digits[0] != "0":
        raise InvalidGTIN("This is a case or pallet code, not a product barcode.")
    if not check_digit_ok(digits):
        raise InvalidGTIN("The check digit doesn't match. Check the number and try again.")
    return digits[-13:].zfill(13)


def lookup_forms(gtin13: str) -> list[str]:
    """Codes to try against Open Food Facts: GTIN-13 first, then UPC-A if applicable."""
    forms = [gtin13]
    if gtin13.startswith("0"):
        forms.append(gtin13[1:])
    return forms
