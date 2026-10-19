"""Estimates from the ingredient list (specs/014). Pure functions, no I/O.

Conservative by design: only what the label states is used, so an estimate never makes a
product look better than its label supports.
"""

import re
from dataclasses import dataclass

from app.scoring.config import EstimatesConfig

_PREFIX = re.compile(r"^\s*ingredients?\s*[:.-]\s*", re.IGNORECASE)
_PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_BRACKETS = re.compile(r"[(\[{].*?[)\]}]")
_NON_WORD = re.compile(r"[^a-z0-9%]+")


@dataclass(frozen=True)
class Ingredient:
    text: str  # lowercase, sub-ingredients in brackets kept
    name: str  # without bracketed sub-ingredients or percentages, single spaces
    percent: float | None


def _words(text: str) -> str:
    return " " + _NON_WORD.sub(" ", text.lower()).strip() + " "


def _has(text: str, phrase: str) -> bool:
    return f" {phrase} " in text


def split_ingredients(text: str | None) -> list[Ingredient]:
    """Top-level ingredients with any stated percentage (EST-1)."""
    if not text:
        return []
    body = _PREFIX.sub("", text.strip())
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in body:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if ch in ",;" and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    out = []
    for raw in parts:
        piece = raw.strip().strip(".*:").strip().lower()
        if not piece:
            continue
        outer = _BRACKETS.sub(" ", piece)
        pct = _PERCENT.search(outer) or _PERCENT.search(piece)
        percent = float(pct.group(1).replace(",", ".")) if pct else None
        name = _NON_WORD.sub(" ", _PERCENT.sub(" ", outer)).strip()
        out.append(Ingredient(piece, name, percent))
    return out


def _is_fvl(ingredient: Ingredient, cfg: EstimatesConfig) -> bool:
    name = _words(ingredient.name)
    if any(_has(name, w) for w in cfg.fvl_exclude):
        return False
    return any(_has(name, w) for w in cfg.fvl_words)


def estimate_fvl(ingredients: list[Ingredient], cfg: EstimatesConfig) -> float | None:
    """Lower-bound fruit/vegetable/legume %, or None if nothing to go on (EST-2)."""
    if not ingredients:
        return None
    if len(ingredients) == 1 and _is_fvl(ingredients[0], cfg):
        return 100.0
    total = sum(i.percent or 0.0 for i in ingredients if _is_fvl(i, cfg))
    return min(round(total, 2), 100.0)


@dataclass(frozen=True)
class NovaEstimate:
    group: int
    marker: str | None  # the ingredient phrase that made it NOVA 4


def estimate_nova(ingredients: list[Ingredient], cfg: EstimatesConfig) -> NovaEstimate | None:
    """NOVA group from ingredient markers, or None with no ingredients (EST-3)."""
    nova = cfg.nova
    relevant = [i for i in ingredients if i.name not in nova.ignore]
    if not relevant:
        return None
    for ingredient in relevant:
        text = _words(ingredient.text)
        for marker in nova.ultra_markers:
            if _has(text, marker):
                return NovaEstimate(4, marker)

    def culinary(i: Ingredient) -> bool:
        return any(_has(_words(i.name), c) for c in nova.culinary)

    if all(culinary(i) for i in relevant):
        return NovaEstimate(2, None)
    if len(relevant) >= 2 and any(culinary(i) for i in relevant):
        return NovaEstimate(3, None)
    return NovaEstimate(1, None)


def find_additive_codes(text: str | None, names: dict[str, str]) -> list[str]:
    """Additive codes whose name or E-number appears as whole words (EST-5).

    `names` maps code ("e250") to its taxonomy name ("E250 - Sodium nitrite").
    """
    if not text:
        return []
    words = _words(text)
    found = set()
    for code, name in names.items():
        plain = _words(re.sub(r"^e\s?\d+[a-z]*(\([ivx]+\))?\s*[-:]\s*", "", name, flags=re.I))
        if (plain.strip() and _has(words, plain.strip())) or _has(words, code):
            found.add(code)
    return sorted(found)
