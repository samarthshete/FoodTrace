"""US regulatory status of additives from FDA's Substances Added to Food inventory (specs/013).

The inventory is a US government work. Its export is a CSV (despite the .xls endpoint name)
with a short preamble before the header row.
"""

import csv
import html
import io
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

EXPORT_URL = (
    "https://www.hfpappexternal.fda.gov/scripts/fdcc/cfc/XMLService.cfm"
    "?method=downloadxls&set=FoodSubstances"
)
CACHE = Path("data/reference/fda_substances.csv")
# FDA-2: statuses from highest to lowest priority, with the CFR parts that give each.
PARTS = [
    ("prohibited", {"189"}),
    ("food_additive", {"172", "173", "180"}),
    ("color_additive", {"73", "74"}),
    ("gras", {"182", "184", "186"}),
    ("prior_sanctioned", {"181"}),
]
_SECTION = re.compile(r"(\d+)\.\d+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_E_PREFIX = re.compile(r"^e\s?\d+[a-z]*(\([ivx]+\))?\s*[-:]\s*", re.IGNORECASE)


class FDAUnavailable(Exception):
    """FDA's export couldn't be fetched, or wasn't the inventory (FDA-7)."""


HEADER = "CAS Reg No"


@dataclass(frozen=True)
class UsStatus:
    status: str
    cfr_ref: str | None


def download(user_agent: str, dest: Path = CACHE) -> Path:  # FDA-1
    """Fetch the export and cache it, only if it really is the inventory (FDA-7)."""
    try:
        resp = httpx.get(EXPORT_URL, headers={"User-Agent": user_agent}, timeout=60,
                         follow_redirects=True)  # fmt: skip
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise FDAUnavailable(f"download failed: {exc.__class__.__name__}") from exc
    if HEADER.encode() not in resp.content:
        raise FDAUnavailable("the response isn't the Substances Added to Food export")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return dest


def normalize_name(name: str) -> str:
    """Lowercased, HTML and punctuation removed, single spaces (FDA-3)."""
    return _NON_ALNUM.sub(" ", html.unescape(name).lower()).strip()


def additive_name(taxonomy_name: str) -> str:
    """'E250 - Sodium nitrite' -> 'sodium nitrite'."""
    return normalize_name(_E_PREFIX.sub("", taxonomy_name.strip()))


def _cell(raw: str) -> str:
    """Cells look like ' 172.170' or '=T("172.170")'."""
    return raw.strip().removeprefix('=T("').removesuffix('")').strip()


def status_of(substance: str, sections: list[str], fema: str) -> UsStatus | None:
    """One status per substance, highest priority first (FDA-2)."""
    if substance.rstrip().upper().endswith("DELISTED"):
        return UsStatus("delisted", None)
    by_part = [(m.group(1), s) for s in sections if (m := _SECTION.match(s))]
    for status, parts in PARTS:
        hits = [s for part, s in by_part if part in parts]
        if hits:
            return UsStatus(status, hits[0])
    return UsStatus("gras_flavor", None) if fema else None


def parse(text: str) -> dict[str, UsStatus]:
    """Normalized substance name and other names -> status (FDA-2, FDA-3)."""
    if HEADER not in text:
        raise FDAUnavailable("the cached file isn't the Substances Added to Food export")
    rows = csv.reader(io.StringIO(text[text.index(HEADER) :]))
    header = next(rows)
    reg_cols = [
        i for i, h in enumerate(header) if h.startswith("Reg ") and h != "Reg Administrative"
    ]
    at = {h.strip(): i for i, h in enumerate(header)}
    index: dict[str, UsStatus] = {}
    for row in rows:
        if len(row) < len(header):
            continue
        substance = _cell(row[at["Substance"]])
        sections = [c for i in reg_cols if (c := _cell(row[i]))]
        status = status_of(substance, sections, _cell(row[at["FEMA No"]]))
        if status is None:
            continue
        others = re.split(r"<br\s*/?>", row[at["Other Names"]])
        for name in [substance, *others]:
            key = normalize_name(name.replace("&diams;", ""))
            if key and key not in index:
                index[key] = status
    return index


def load(path: Path = CACHE) -> dict[str, UsStatus]:
    return parse(path.read_text(encoding="utf-8", errors="replace"))
