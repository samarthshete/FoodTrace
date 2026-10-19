"""`POST /contributions`: add a missing product from a label photo (specs/017)."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import insert

from app.auth import MaybeUserId
from app.db.models import Contribution, Product
from app.problems import Problem
from app.routers.products import Session, get_now, product_body
from app.scoring.config import ScoringConfig, default_config
from app.services.contributions import ContributionIn, RateLimiter, off_fields, product_row
from app.services.gtin import InvalidGTIN, normalize
from app.services.lookup import LookupResult, product_additives, score_product, upsert_product
from app.services.off_client import share_product
from app.settings import Settings, get_settings

router = APIRouter(tags=["contributions"])


def get_limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter | None = getattr(request.app.state, "contribution_limiter", None)
    if limiter is None:
        limiter = RateLimiter(get_settings().contributions_per_hour)
        request.app.state.contribution_limiter = limiter
    return limiter


def client_key(request: Request) -> str:
    """The web app forwards the browser's address; direct callers use their own. Not stored."""
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


@router.get("/contributions/config")
async def contribution_config(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, bool]:
    """Whether to offer sharing with Open Food Facts (CONTRIB-9)."""
    return {"can_share_with_off": bool(settings.off_user and settings.off_password)}


@router.post("/contributions", status_code=201)
async def contribute(
    body: ContributionIn,
    request: Request,
    response: Response,
    session: Session,
    cfg: Annotated[ScoringConfig, Depends(default_config)],
    settings: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[RateLimiter, Depends(get_limiter)],
    now: Annotated[datetime, Depends(get_now)],
    user_id: MaybeUserId,
) -> dict[str, Any]:
    try:
        gtin = normalize(body.gtin)  # CONTRIB-4
    except InvalidGTIN as exc:
        raise Problem(422, "Invalid barcode", str(exc)) from exc
    if not limiter.allow(client_key(request)):  # CONTRIB-8
        raise Problem(429, "Too many contributions", "Please try again in an hour.")
    if await session.get(Product, gtin) is not None:  # CONTRIB-5
        raise Problem(409, "Product already exists",
                      "This product is already in the database.", gtin=gtin)  # fmt: skip

    await upsert_product(session, product_row(gtin, body, now), None, cfg.engine_version)
    shared = None
    if body.share_with_off and settings.off_user and settings.off_password:  # CONTRIB-10
        shared = await share_product(request.app.state.http, settings.off_base_url,
                                     settings.user_agent, settings.off_user,
                                     settings.off_password, off_fields(gtin, body))  # fmt: skip
    extracted = body.model_dump(exclude={"share_with_off"})
    await session.execute(insert(Contribution).values(
        gtin=gtin, extracted=extracted, status="accepted", shared_with_off=shared,
        user_id=user_id,  # ACC-18: linked when signed in
    ))  # fmt: skip
    await session.commit()  # CONTRIB-6
    product = await session.get(Product, gtin, populate_existing=True)
    assert product is not None
    result = LookupResult(product, await score_product(session, product, cfg), stale=False)
    out = product_body(result)
    out["additives"] = await product_additives(session, gtin)
    out["shared_with_off"] = shared
    response.headers["Location"] = f"/products/{gtin}"
    return out
