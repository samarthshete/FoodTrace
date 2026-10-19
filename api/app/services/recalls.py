"""Match openFDA recall records to a product (specs/010).

Two kinds of match: the product's barcode is listed in the record (RECALL-5), or its brand
and name words appear in it (RECALL-6). Matching is deliberately conservative: a false
"related recall" banner is worse than a missed one.
"""

import re
import unicodedata
from typing import Any, Literal
from urllib.parse import quote

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Product, Recall, RecallSync
from app.scoring.config import RecallsConfig
from app.services.gtin import InvalidGTIN, normalize

Match = Literal["code", "brand_name"]
SOURCE = "openfda"
OPENFDA_RECORD = "https://api.fda.gov/food/enforcement.json?search=recall_number:"
_DIGIT_GAP = re.compile(r"(?<=\d)[ \-](?=\d)")
_DIGIT_RUN = re.compile(r"(?<!\d)(\d{12,13})(?!\d)")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def extract_codes(*texts: str | None) -> list[str]:
    """Every valid 12- or 13-digit code in the texts, as sorted GTIN-13s (RECALL-3)."""
    codes: set[str] = set()
    for text in texts:
        for run in _DIGIT_RUN.findall(_DIGIT_GAP.sub("", text or "")):
            try:
                codes.add(normalize(run))
            except InvalidGTIN:
                continue
    return sorted(codes)


def normalize_text(text: str | None) -> str:
    """Lowercase, accents and punctuation stripped, single spaces."""
    ascii_text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return _NON_ALNUM.sub(" ", ascii_text.lower()).strip()


def _has_phrase(haystack: str, phrase: str) -> bool:
    return f" {phrase} " in f" {haystack} "


def eligible_brand(brand: str | None, cfg: RecallsConfig) -> str | None:
    """The normalized first brand, or None if it may only match by code (RECALL-7)."""
    first = normalize_text((brand or "").split(",")[0])
    if len(first.replace(" ", "")) < 3:
        return None
    if first in {normalize_text(b) for b in cfg.generic_brands}:
        return None
    return first


def name_words(name: str | None, brand: str, cfg: RecallsConfig) -> list[str]:
    """Distinctive words of the product name (RECALL-6)."""
    skip = set(brand.split()) | set(cfg.stop_words)
    words = [w for w in normalize_text(name).split() if len(w) >= 3 and w not in skip]
    return list(dict.fromkeys(words))


def match(product: Product, recall: Recall, cfg: RecallsConfig) -> Match | None:
    if product.gtin in recall.codes:  # RECALL-5
        return "code"
    brand = eligible_brand(product.brand, cfg)
    if brand is None:
        return None
    words = name_words(product.name, brand, cfg)
    if not words:  # no name to match on (RECALL-7)
        return None
    description = normalize_text(recall.product_description)
    if not (
        _has_phrase(description, brand) or _has_phrase(normalize_text(recall.recalling_firm), brand)
    ):
        return None
    found = sum(1 for w in words if _has_phrase(description, w))
    return "brand_name" if found >= min(2, len(words)) else None


def record_url(recall_number: str) -> str:
    return OPENFDA_RECORD + quote(f'"{recall_number}"')


def _as_dict(kind: Match, r: Recall) -> dict[str, Any]:  # RECALL-9
    started = r.recall_initiation_date
    return {
        "recall_number": r.recall_number,
        "match": kind,
        "classification": r.classification,
        "status": r.status,
        "reason_for_recall": r.reason_for_recall,
        "recall_initiation_date": started.isoformat() if started else None,
        "product_description": r.product_description,
        "url": record_url(r.recall_number),
    }


def _order(found: tuple[Match, Recall]) -> tuple[bool, int, str]:
    """Code matches first, then newest first, then recall number (RECALL-10)."""
    kind, r = found
    started = r.recall_initiation_date.toordinal() if r.recall_initiation_date else 0
    return (kind != "code", -started, r.recall_number)


async def find_recalls(
    session: AsyncSession, product: Product, cfg: RecallsConfig
) -> list[dict[str, Any]]:
    conditions = [Recall.codes.contains([product.gtin])]
    if (brand := eligible_brand(product.brand, cfg)) is not None:
        # Cheap SQL prefilter on the brand's longest word; match() makes the real decision.
        probe = f"%{max(brand.split(), key=len)}%"
        conditions.append(
            or_(Recall.product_description.ilike(probe), Recall.recalling_firm.ilike(probe))
        )
    rows = await session.scalars(select(Recall).where(or_(*conditions)))
    found = [(kind, r) for r in rows if (kind := match(product, r, cfg)) is not None]
    found.sort(key=_order)
    return [_as_dict(kind, r) for kind, r in found[: cfg.limit]]


async def recalls_as_of(session: AsyncSession) -> str | None:
    sync = await session.get(RecallSync, SOURCE)
    return sync.as_of.isoformat() if sync else None
