"""Integration fixtures: a real Postgres (ofs_test) and a mocked Open Food Facts."""

import os
import subprocess
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.session import get_session, make_engine, make_sessionmaker
from app.main import app
from app.routers.products import get_now
from app.services.off_client import OFFClient
from app.services.usda_client import USDAClient

ROOT = Path(__file__).resolve().parents[3]
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://ofs:ofs@localhost:5432/ofs_test"
)
OFF_BASE = "https://off.test"
USDA_BASE = "https://usda.test"
NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
USER_AGENT = "FoodTrace/0.1 (tests@example.com)"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def migrated_db() -> str:
    env = {**os.environ, "DATABASE_URL": TEST_DB_URL}
    proc = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"], cwd=ROOT, env=env,
        capture_output=True, text=True,
    )  # fmt: skip
    if proc.returncode != 0:
        if os.environ.get("CI"):
            pytest.fail(f"Migrations failed in CI:\n{proc.stderr}")
        pytest.skip(f"Postgres not reachable (run: docker compose up -d db)\n{proc.stderr[-300:]}")
    return TEST_DB_URL


@pytest.fixture(scope="session")
async def engine(migrated_db: str) -> AsyncIterator[AsyncEngine]:
    eng = make_engine(migrated_db)
    yield eng
    await eng.dispose()


@pytest.fixture
async def sessionmaker(engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE products, scores, product_additives, additives CASCADE"))
        await conn.execute(text(
            "INSERT INTO additives (code, name, risk_level, evidence_grade, efsa_url) VALUES "
            "('e250', 'E250 - Sodium nitrite', 3, 'A', 'https://doi.org/e250'), "
            "('e330', 'E330 - Citric acid', NULL, 'B', NULL)"
        ))  # fmt: skip
    yield make_sessionmaker(engine)


@pytest.fixture
def off_mock() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=OFF_BASE, assert_all_called=False) as mock:
        yield mock


@pytest.fixture
def usda_mock() -> Iterator[respx.MockRouter]:
    """USDA has nothing unless a test says otherwise."""
    with respx.mock(base_url=USDA_BASE, assert_all_called=False) as mock:
        mock.get("/fdc/v1/foods/search", name="search").respond(200, json={"foods": []})
        yield mock


@pytest.fixture
async def client(
    sessionmaker: async_sessionmaker[AsyncSession],
    off_mock: respx.MockRouter,
    usda_mock: respx.MockRouter,
) -> AsyncIterator[httpx.AsyncClient]:
    async def _session() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_now] = lambda: NOW
    async with httpx.AsyncClient() as off_http:
        app.state.http = off_http
        app.state.response_cache = None  # specs/025: every test sees the database
        app.state.off = OFFClient(off_http, OFF_BASE, USER_AGENT)
        app.state.usda = USDAClient(off_http, USDA_BASE, "TEST_KEY", USER_AGENT)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://api") as c:
            yield c
    app.dependency_overrides.clear()


def off_product(code: str = "0036000291452", **overrides: Any) -> dict[str, Any]:
    """A realistic OFF v2 payload: the worked SNACK example from the unit tests."""
    product: dict[str, Any] = {
        "code": code,
        "product_name": "Crunchy Oat Bars",
        "brands": "Acme Foods, Acme",
        "categories_tags": ["en:snacks", "en:sweet-snacks", "en:cereal-bars"],
        "image_front_url": "https://images.off.test/front.jpg",
        "ingredients_text": "Oats, sugar, salt, sodium nitrite, citric acid",
        "nutriments": {
            "energy-kj_100g": 1500, "sugars_100g": 12, "saturated-fat_100g": 2.5,
            "salt_100g": 0.9, "fiber_100g": 4.5, "proteins_100g": 8, "fat_100g": 9,
            "fruits-vegetables-legumes-estimate-from-ingredients_100g": 0,
        },
        "nova_group": 4,
        "labels_tags": ["en:no-gluten"],
        "additives_tags": ["en:e250", "en:e330"],
    }  # fmt: skip
    product.update(overrides)
    return {"status": 1, "product": product}


NOT_FOUND = {"status": 0, "status_verbose": "product not found"}
