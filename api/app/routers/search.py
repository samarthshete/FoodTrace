"""`GET /search` (specs/016)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.problems import Problem
from app.scoring.config import ScoringConfig, default_config
from app.services import search as search_service
from app.services.gtin import InvalidGTIN, normalize

router = APIRouter(tags=["search"])


@router.get("/search")
async def search(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    cfg: Annotated[ScoringConfig, Depends(default_config)],
    q: Annotated[str, Query()] = "",
    limit: Annotated[int | None, Query()] = None,
) -> dict[str, Any]:
    query = q.strip()
    if not 2 <= len(query) <= 100:  # SEARCH-1
        raise Problem(422, "Invalid search", "Type 2 to 100 characters to search.")
    response.headers["Cache-Control"] = "public, max-age=300"  # SEARCH-6
    if query.isdigit():
        try:
            return {"q": query, "gtin": normalize(query), "results": []}  # SEARCH-3
        except InvalidGTIN:
            pass
    results = await search_service.search(
        session, query, search_service.clamp_limit(limit), cfg.engine_version
    )
    return {"q": query, "gtin": None, "results": results}
