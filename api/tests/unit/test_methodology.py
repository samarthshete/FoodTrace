import re
from pathlib import Path

import httpx
import pytest

from app.main import app
from app.scoring.config import default_config

spec = pytest.mark.spec
SPEC_005 = Path(__file__).resolve().parents[3] / "specs" / "005-engine.md"


async def get() -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://api"
    ) as c:
        return await c.get("/methodology")


@spec("METH-1")
async def test_methodology_numbers_come_from_the_scoring_config() -> None:
    r = await get()
    cfg = default_config()
    body = r.json()
    assert r.headers["cache-control"] == "public, max-age=3600"
    assert body["engine_version"] == cfg.engine_version
    assert body["weights"] == {"nutrition": 60, "additives": 30, "processing": 10}
    assert [b["id"] for b in body["bands"]] == ["excellent", "good", "mediocre", "poor"]
    assert body["nova_values"]["4"] == 0.0 and body["additives"]["cap_total"] == 49
    assert body["sources"]["nova"].startswith("https://")


@spec("METH-2")
async def test_changelog_matches_spec_005_and_ends_at_the_current_version() -> None:
    table = re.findall(r"^\| (\d+\.\d+\.\d+) \| (.+?) \|$", SPEC_005.read_text(), re.MULTILINE)
    body = (await get()).json()
    assert [(e["version"], e["change"]) for e in body["changelog"]] == table
    assert body["changelog"][-1]["version"] == default_config().engine_version
