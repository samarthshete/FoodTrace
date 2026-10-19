"""`GET /explore` and `GET /explore/{id}` (specs/024)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.problems import Problem
from app.scoring.config import ScoringConfig, default_config
from app.services import explore as svc

router = APIRouter(tags=["explore"])
CACHE = "public, max-age=600"


@router.get("/explore")
async def explore(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    cfg: Annotated[ScoringConfig, Depends(default_config)],
    per_category: Annotated[int | None, Query()] = None,
) -> dict[str, Any]:
    n = svc.clamp(per_category, svc.PER_CATEGORY_DEFAULT, svc.PER_CATEGORY_MAX)  # EXPLORE-2
    response.headers["Cache-Control"] = CACHE
    categories = await svc.explore(session, cfg.engine_version, n)
    return {"engine_version": cfg.engine_version, "categories": categories}


@router.get("/explore/{group_id}")
async def explore_group(
    group_id: str,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    cfg: Annotated[ScoringConfig, Depends(default_config)],
    limit: Annotated[int | None, Query()] = None,
) -> dict[str, Any]:
    group = svc.BY_ID.get(group_id)
    if group is None:  # EXPLORE-5
        raise Problem(404, "Unknown category", f"There's no category called {group_id!r}.")
    n = svc.clamp(limit, svc.LIMIT_DEFAULT, svc.LIMIT_MAX)
    response.headers["Cache-Control"] = CACHE
    return await svc.explore_group(session, cfg.engine_version, group, n)
