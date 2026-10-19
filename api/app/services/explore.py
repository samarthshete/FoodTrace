"""Top foods per category (specs/024). Database only: never calls a live source."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

PER_CATEGORY_DEFAULT, PER_CATEGORY_MAX = 6, 24
LIMIT_DEFAULT, LIMIT_MAX = 24, 60


@dataclass(frozen=True)
class Group:
    id: str
    label: str
    blurb: str
    tags: tuple[str, ...]


# EXPLORE-1: fixed groups of Open Food Facts primary categories, in display order.
GROUPS: tuple[Group, ...] = (
    Group("breakfast", "Breakfast cereals", "Cereals, mueslis and oats for the morning.",
          ("en:breakfast-cereals", "en:extruded-cereals", "en:mueslis", "en:rolled-oats")),
    Group("yogurts", "Yogurts", "Plain, flavoured and Greek-style yogurts.",
          ("en:yogurts", "en:greek-style-yogurts")),
    Group("breads", "Breads", "Sliced loaves, bagels and buns.",
          ("en:breads", "en:wheat-breads", "en:bagel-breads", "en:hamburger-buns")),
    Group("snacks", "Chips & salty snacks", "Crisps, corn chips, pretzels and crackers.",
          ("en:potato-crisps", "en:corn-chips", "en:salted-snacks", "en:pretzel",
           "en:crackers-appetizers")),
    Group("bars", "Snack & protein bars", "Granola, cereal and protein bars.",
          ("en:protein-bars", "en:cereal-bars", "en:bars")),
    Group("sweets", "Cookies & sweets", "Cookies, cakes, candy and chocolate.",
          ("en:biscuits", "en:cakes", "en:candies",
           "en:chocolate-candies")),
    Group("drinks", "Drinks", "Sodas, juices, milks and plant-based drinks.",
          ("en:sweetened-beverages", "en:beverages", "en:milks", "en:plant-based-beverages",
           "en:protein-shakes")),
    Group("cheese", "Cheese", "Sliced, shredded and block cheeses.", ("en:cheeses",)),
    Group("meals", "Pasta, soups & meals", "Pasta, soups, pizzas and ready meals.",
          ("en:pastas", "en:meals", "en:pizzas", "en:soups", "en:canned-soups",
           "en:frozen-foods")),
    Group("spreads", "Spreads & pantry", "Peanut butter, honey, beans and eggs.",
          ("en:peanut-butters", "en:honeys", "en:canned-common-beans", "en:eggs")),
)  # fmt: skip
BY_ID = {g.id: g for g in GROUPS}

# Tag -> group, built from the constants above (never from input), as a VALUES list.
_TAG_ROWS = ", ".join(f"('{tag}', '{g.id}', {i})" for i, g in enumerate(GROUPS) for tag in g.tags)

# EXPLORE-2/3: one query for every group, ranked inside each group.
_RANKED = f"""
    WITH tags(tag, group_id, position) AS (VALUES {_TAG_ROWS}),
    ranked AS (
      SELECT t.group_id, t.position, p.gtin, p.name, p.brand, p.image_url, p.nova_group,
             s.total, s.breakdown -> 'band' AS band,
             s.breakdown -> 'nutriscore' ->> 'grade' AS nutriscore_grade,
             ROW_NUMBER() OVER (
               PARTITION BY t.group_id
               ORDER BY p.image_url IS NULL, s.total DESC, p.completeness DESC NULLS LAST, p.gtin
             ) AS rank
      FROM products p
      JOIN tags t ON t.tag = p.primary_category
      JOIN scores s ON s.gtin = p.gtin AND s.engine_version = :version
      WHERE s.total IS NOT NULL AND coalesce(btrim(p.name), '') <> ''
        AND (CAST(:group_id AS text) IS NULL OR t.group_id = :group_id)
    )
    SELECT * FROM ranked WHERE rank <= :limit ORDER BY position, rank
"""  # the VALUES list comes from constants, never from input
RANKED_SQL = text(_RANKED)


def clamp(value: int | None, default: int, maximum: int) -> int:
    return default if value is None else max(1, min(maximum, value))


def _item(r: Any) -> dict[str, Any]:
    grade = r.nutriscore_grade if r.nutriscore_grade in ("a", "b", "c", "d", "e") else None
    return {
        "gtin": r.gtin,
        "name": r.name,
        "brand": r.brand,
        "image_url": r.image_url,
        "total": r.total,
        "band": r.band,
        "nutriscore_grade": grade,
        "nova_group": r.nova_group,
    }


def _group(g: Group, products: list[dict[str, Any]]) -> dict[str, Any]:
    return {"id": g.id, "label": g.label, "blurb": g.blurb, "products": products}


async def _ranked(
    session: AsyncSession, version: str, limit: int, group_id: str | None
) -> dict[str, list[dict[str, Any]]]:
    params = {"version": version, "limit": limit, "group_id": group_id}
    found: dict[str, list[dict[str, Any]]] = {g.id: [] for g in GROUPS}
    for r in await session.execute(RANKED_SQL, params):
        found[r.group_id].append(_item(r))
    return found


async def explore(session: AsyncSession, version: str, per_category: int) -> list[dict[str, Any]]:
    found = await _ranked(session, version, per_category, None)
    return [_group(g, found[g.id]) for g in GROUPS]


async def explore_group(
    session: AsyncSession, version: str, group: Group, limit: int
) -> dict[str, Any]:
    found = await _ranked(session, version, limit, group.id)
    return _group(group, found[group.id])
