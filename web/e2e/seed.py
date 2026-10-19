"""Seed the e2e database (ofs_test) with fresh products, scores and a recall, so the e2e run
needs no Open Food Facts or openFDA call.

Run from the repo root: uv run python web/e2e/seed.py
"""

import asyncio
import json
import os
from datetime import UTC, datetime

import httpx
from sqlalchemy import text

from app.db.session import make_engine, make_sessionmaker
from app.scoring.config import default_config
from app.services.lookup import lookup
from app.services.off_client import OFFClient
from pipeline.recalls import rows_in_window, sync

URL = os.environ["DATABASE_URL"]
NUTRITION = {
    "energy_kj": 1500, "sugars_g": 12, "saturated_fat_g": 2.5, "salt_g": 0.9,
    "fiber_g": 4.5, "proteins_g": 8, "fvl_percent": 0,
}  # fmt: skip

PRODUCT = """
INSERT INTO products (gtin, name, brand, primary_category, categories, image_url, ingredients_text,
  nutrition, nova_group, labels, is_organic, additives_known, source_by_field, completeness,
  fetched_at)
VALUES ('0036000291452', 'Crunchy Oat Bars', 'Acme Foods', 'en:cereal-bars',
  ARRAY['en:snacks', 'en:cereal-bars'], NULL, 'Oats, sugar, salt, sodium nitrite, citric acid',
  CAST(:nutrition AS jsonb),
  4, ARRAY[]::text[], false, true, '{"name": "off"}', 0.89, :now)
"""

# A better-scored cereal bar for the alternatives strip (spec 009): no additives, NOVA 1.
ALTERNATIVE_GTIN = "0000000000017"
ALTERNATIVE = """
INSERT INTO products (gtin, name, brand, primary_category, categories, ingredients_text,
  nutrition, nova_group, additives_known, completeness, fetched_at)
VALUES (:gtin, 'Plain Oat Bars', 'Good Grain', 'en:cereal-bars',
  ARRAY['en:snacks', 'en:cereal-bars'], 'Oats, dates', CAST(:nutrition AS jsonb), 1, true, 1, :now)
"""
ALTERNATIVE_NUTRITION = {
    "energy_kj": 1400, "sugars_g": 3, "saturated_fat_g": 0.5, "salt_g": 0.05,
    "fiber_g": 9, "proteins_g": 12, "fvl_percent": 0,
}  # fmt: skip

# A recall that matches the oat bars by brand and name (spec 010).
RECALL = {
    "recall_number": "F-0001-2026", "status": "Ongoing", "classification": "Class II",
    "recalling_firm": "Acme Foods Inc",
    "product_description": "Acme Foods Crunchy Oat Bars, 6 ct, 7.4 oz box",
    "reason_for_recall": "Undeclared peanut", "recall_initiation_date": "20260801",
    "report_date": "20260901",
}  # fmt: skip


def as_nutrition(values: dict[str, float]) -> str:
    return json.dumps({k: {"value": v, "estimated": False} for k, v in values.items()})


async def main() -> None:
    engine = make_engine(URL)
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE products, scores, product_additives, recalls, recall_sync CASCADE")
        )
        await conn.execute(
            text(PRODUCT),
            {
                "now": datetime.now(UTC),
                "nutrition": json.dumps(
                    {k: {"value": v, "estimated": k == "fvl_percent"} for k, v in NUTRITION.items()}
                ),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO product_additives (gtin, additive_code) VALUES "
                "('0036000291452', 'e250'), ('0036000291452', 'e330')"
            )
        )
        await conn.execute(
            text(ALTERNATIVE),
            {
                "gtin": ALTERNATIVE_GTIN,
                "now": datetime.now(UTC),
                "nutrition": as_nutrition(ALTERNATIVE_NUTRITION),
            },
        )

    now = datetime.now(UTC)
    async with make_sessionmaker(engine)() as session, httpx.AsyncClient() as http:
        # Both products are fresh, so lookup() scores them without calling OFF.
        off = OFFClient(http, "http://127.0.0.1:9", "FoodTrace/e2e")
        for gtin in ("0036000291452", ALTERNATIVE_GTIN):
            await lookup(session, gtin, off, default_config(), now, cache_days=30)
        await sync(session, rows_in_window([RECALL], now.date(), 3), now)
    await engine.dispose()


asyncio.run(main())
