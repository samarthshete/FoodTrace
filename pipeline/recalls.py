"""Sync openFDA food enforcement (recall) records into `recalls` (specs/010, RECALL-1..4).

Usage: uv run python -m pipeline.recalls
Downloads the bulk file listed in api.fda.gov/download.json (~6 MB zipped). It does not page
through the live API.
"""

import asyncio
import io
import json
import zipfile
from datetime import UTC, date, datetime
from typing import Any, cast

import httpx
from sqlalchemy import Table, delete, not_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Recall, RecallSync
from app.db.session import make_engine, make_sessionmaker
from app.scoring.config import default_config
from app.services.recalls import SOURCE, extract_codes
from app.settings import get_settings

DOWNLOAD_INDEX = "https://api.fda.gov/download.json"
CHUNK = 1000  # rows per INSERT, well under asyncpg's parameter limit


def partition_urls(index: dict[str, Any]) -> list[str]:
    parts = index["results"]["food"]["enforcement"]["partitions"]
    return [p["file"] for p in parts]


def parse_date(raw: str | None) -> date | None:
    """openFDA dates are YYYYMMDD strings."""
    try:
        return datetime.strptime(raw or "", "%Y%m%d").date()
    except ValueError:
        return None


def window_start(today: date, years: int) -> date:
    try:
        return today.replace(year=today.year - years)
    except ValueError:  # 29 February
        return today.replace(year=today.year - years, day=28)


def to_row(record: dict[str, Any]) -> dict[str, Any] | None:
    number, reported = record.get("recall_number"), parse_date(record.get("report_date"))
    if not number or reported is None:
        return None
    description = record.get("product_description") or ""
    code_info, more = record.get("code_info"), record.get("more_code_info")
    return {
        "recall_number": number,
        "event_id": record.get("event_id"),
        "status": record.get("status"),
        "classification": record.get("classification"),
        "recalling_firm": record.get("recalling_firm"),
        "product_description": description,
        "code_info": code_info,
        "more_code_info": more,
        "reason_for_recall": record.get("reason_for_recall"),
        "recall_initiation_date": parse_date(record.get("recall_initiation_date")),
        "report_date": reported,
        "codes": extract_codes(description, code_info, more),  # RECALL-3
    }


def rows_in_window(records: list[dict[str, Any]], today: date, years: int) -> list[dict[str, Any]]:
    """Rows reported within the window, one per recall number (RECALL-2)."""
    start = window_start(today, years)
    rows = {}
    for record in records:
        row = to_row(record)
        if row is not None and row["report_date"] >= start:
            rows[row["recall_number"]] = row
    return list(rows.values())


async def sync(session: AsyncSession, rows: list[dict[str, Any]], now: datetime) -> None:
    """Make `recalls` mirror `rows` and record `as_of`. Idempotent (RECALL-4)."""
    table = cast(Table, Recall.__table__)
    for i in range(0, len(rows), CHUNK):
        stmt = insert(table).values(rows[i : i + CHUNK])
        update = {c.name: stmt.excluded[c.name] for c in table.columns if c.name != "recall_number"}
        await session.execute(
            stmt.on_conflict_do_update(index_elements=["recall_number"], set_=update)
        )
    numbers = [r["recall_number"] for r in rows]
    await session.execute(delete(Recall).where(not_(Recall.recall_number.in_(numbers))))
    stmt = insert(cast(Table, RecallSync.__table__)).values(source=SOURCE, as_of=now)
    await session.execute(
        stmt.on_conflict_do_update(index_elements=["source"], set_={"as_of": now})
    )
    await session.commit()


def download(user_agent: str) -> list[dict[str, Any]]:
    headers = {"User-Agent": user_agent}  # RECALL-1
    with httpx.Client(headers=headers, timeout=60, follow_redirects=True) as http:
        index = http.get(DOWNLOAD_INDEX).raise_for_status().json()
        records: list[dict[str, Any]] = []
        for url in partition_urls(index):
            archive = zipfile.ZipFile(io.BytesIO(http.get(url).raise_for_status().content))
            for name in archive.namelist():
                records.extend(json.loads(archive.read(name))["results"])
    return records


async def run(database_url: str, records: list[dict[str, Any]], now: datetime) -> int:
    rows = rows_in_window(records, now.date(), default_config().recalls.window_years)
    engine = make_engine(database_url)
    async with make_sessionmaker(engine)() as session:
        await sync(session, rows, now)
    await engine.dispose()
    return len(rows)


def main() -> None:
    settings = get_settings()
    records = download(settings.user_agent)
    kept = asyncio.run(run(settings.database_url, records, datetime.now(UTC)))
    print(f"recalls: {len(records)} openFDA records, {kept} in the window")


if __name__ == "__main__":
    main()
