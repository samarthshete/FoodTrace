from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import problems, response_cache
from app.db.session import make_engine, make_sessionmaker
from app.routers import contributions, explore, me, methodology, products, search
from app.services.off_client import OFFClient
from app.services.usda_client import USDAClient
from app.settings import APP_VERSION, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    app.state.sessionmaker = make_sessionmaker(engine)
    app.state.response_cache = response_cache.ResponseCache(
        settings.response_cache_ttl_s, settings.response_cache_max
    )
    async with httpx.AsyncClient(timeout=settings.off_timeout_s) as http:
        app.state.http = http
        app.state.off = OFFClient(http, settings.off_base_url, settings.user_agent)
        app.state.usda = USDAClient(
            http, settings.usda_base_url, settings.usda_api_key, settings.user_agent,
            settings.usda_timeout_s,
        )  # fmt: skip
        yield
    await engine.dispose()


app = FastAPI(
    title="FoodTrace API",
    description="AI-Powered Grocery Intelligence Platform",
    version=APP_VERSION,
    lifespan=lifespan,
)
problems.install(app)
response_cache.install(app)
app.include_router(products.router)
app.include_router(search.router)
app.include_router(explore.router)
app.include_router(contributions.router)
app.include_router(me.router)
app.include_router(methodology.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """Report readiness only when the database accepts a query."""
    try:
        async with request.app.state.sessionmaker() as session:
            await session.execute(text("SELECT 1"))
    except (AttributeError, OSError, SQLAlchemyError):
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return JSONResponse({"status": "ok"})
