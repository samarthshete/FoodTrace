import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.main import app

spec = pytest.mark.spec


class FakeSession:
    def __init__(self, available: bool) -> None:
        self.available = available

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, _statement: object) -> None:
        if not self.available:
            raise SQLAlchemyError("database unavailable")


class FakeSessionmaker:
    def __init__(self, available: bool) -> None:
        self.available = available

    def __call__(self) -> FakeSession:
        return FakeSession(self.available)


@spec("DEPLOY-1")
async def test_readiness_checks_the_database() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api") as client:
        app.state.sessionmaker = FakeSessionmaker(available=True)
        response = await client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        app.state.sessionmaker = FakeSessionmaker(available=False)
        response = await client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unavailable"}
