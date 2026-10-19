"""`GET /products/{gtin}`, `/breakdown` (specs/006), `/alternatives` (009), `/recalls` (010)."""

import hashlib
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.problems import Problem
from app.scoring.config import ScoringConfig, default_config
from app.scoring.engine import ScoreResult
from app.scoring.explain import explain
from app.scoring.types import BreakdownLine
from app.services.alternatives import find_alternatives
from app.services.gtin import InvalidGTIN, normalize
from app.services.lookup import LookupResult, ProductNotFound, lookup, product_additives
from app.services.off_client import OFFClient, SourceUnavailable
from app.services.recalls import find_recalls, recalls_as_of
from app.services.usda_client import USDAClient
from app.settings import Settings, get_settings

router = APIRouter(prefix="/products", tags=["products"])
ATTRIBUTION = "Data from Open Food Facts (ODbL)"
RECALL_ATTRIBUTION = "Recall data from openFDA (FDA)"
USDA_ATTRIBUTION = "Nutrition data from USDA FoodData Central"
CACHE_CONTROL = "public, max-age=300"

Session = Annotated[AsyncSession, Depends(get_session)]  # shared with other routers


def get_off(request: Request) -> OFFClient:
    off: OFFClient = request.app.state.off
    return off


def get_usda(request: Request) -> USDAClient | None:
    usda: USDAClient | None = getattr(request.app.state, "usda", None)
    return usda


def get_now() -> datetime:
    return datetime.now(UTC)


async def _resolve(
    raw_gtin: str, session: AsyncSession, off: OFFClient, cfg: ScoringConfig,
    settings: Settings, now: datetime, usda: USDAClient | None = None,
) -> LookupResult:  # fmt: skip
    try:
        gtin = normalize(raw_gtin)  # LOOKUP-1
    except InvalidGTIN as exc:
        raise Problem(422, "Invalid barcode", str(exc)) from exc
    try:
        return await lookup(session, gtin, off, cfg, now, settings.cache_days, usda)
    except ProductNotFound as exc:  # LOOKUP-7
        raise Problem(
            404, "Product not found",
            "We couldn't find this barcode. You can add it by photographing the label.",
            gtin=gtin, next="contribute",
        ) from exc  # fmt: skip
    except SourceUnavailable as exc:  # LOOKUP-8
        raise Problem(503, "Product data source unavailable",
                      "Open Food Facts didn't respond. Try again in a moment.",
                      gtin=gtin) from exc  # fmt: skip


def _etag(result: LookupResult, cfg: ScoringConfig) -> str:  # LOOKUP-11
    key = f"{result.product.gtin}|{cfg.engine_version}|{result.product.fetched_at.isoformat()}"
    return '"' + hashlib.sha256(key.encode()).hexdigest()[:32] + '"'


def _cached(request: Request, response: Response, etag: str) -> Response | None:
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = CACHE_CONTROL
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": CACHE_CONTROL})
    return None


def product_body(result: LookupResult) -> dict[str, Any]:
    p = result.product
    score = {k: v for k, v in result.score.items() if k != "breakdown"}
    return {
        "gtin": p.gtin,
        "name": p.name,
        "brand": p.brand,
        "primary_category": p.primary_category,
        "categories": p.categories,
        "image_url": p.image_url,
        "ingredients_text": p.ingredients_text,
        "nutrition": p.nutrition,
        "nova_group": p.nova_group,
        "labels": p.labels,
        "is_organic": p.is_organic,
        "allergens": p.allergens,  # ACC-6
        "traces": p.traces,
        "ingredients_analysis": p.ingredients_analysis,
        # Known only when OFF analysed an ingredient list; USDA and contributions have none.
        "allergens_known": p.source_by_field.get("ingredients_text") == "off",
        "completeness": float(p.completeness) if p.completeness is not None else None,
        "source_by_field": p.source_by_field,
        "fetched_at": p.fetched_at.isoformat(),
        "stale": result.stale,
        "score": score,
        "attribution": attribution(p.source_by_field),
    }


def attribution(source_by_field: dict[str, str]) -> str:
    """Credit every source the product's data came from (LOOKUP-10, USDA-8)."""
    sources = set(source_by_field.values())
    parts = [ATTRIBUTION] if "off" in sources or not sources else []
    if "usda" in sources:
        parts.append(USDA_ATTRIBUTION)
    return ". ".join(parts)


def _rehydrate(stored: dict[str, Any]) -> ScoreResult:
    """Rebuild a ScoreResult from its stored JSON so explain() can run on it."""
    lines = tuple(
        BreakdownLine(
            rule_id=d["rule_id"], component=d["component"], points=d["points"],
            input_value=d["input_value"], source_url=d["source_url"],
            estimated=d["estimated"], note=d.get("note"),
        )
        for d in stored["breakdown"]
    )  # fmt: skip
    return ScoreResult(
        engine_version=stored["engine_version"], status=stored["status"], total=stored["total"],
        band=stored["band"], confidence=stored["confidence"],
        missing_inputs=tuple(stored["missing_inputs"]), nutriscore=stored["nutriscore"],
        components=stored["components"], breakdown=lines,
    )  # fmt: skip


@router.get("/{gtin}", response_model=None)
async def get_product(
    gtin: str,
    request: Request,
    response: Response,
    session: Session,
    off: Annotated[OFFClient, Depends(get_off)],
    usda: Annotated[USDAClient | None, Depends(get_usda)],
    cfg: Annotated[ScoringConfig, Depends(default_config)],
    settings: Annotated[Settings, Depends(get_settings)],
    now: Annotated[datetime, Depends(get_now)],
) -> dict[str, Any] | Response:
    result = await _resolve(gtin, session, off, cfg, settings, now, usda)
    if (not_modified := _cached(request, response, _etag(result, cfg))) is not None:
        return not_modified
    body = product_body(result)  # LOOKUP-10
    body["additives"] = await product_additives(session, result.product.gtin)  # FDA-5
    return body


@router.get("/{gtin}/breakdown", response_model=None)
async def get_breakdown(
    gtin: str,
    request: Request,
    response: Response,
    session: Session,
    off: Annotated[OFFClient, Depends(get_off)],
    usda: Annotated[USDAClient | None, Depends(get_usda)],
    cfg: Annotated[ScoringConfig, Depends(default_config)],
    settings: Annotated[Settings, Depends(get_settings)],
    now: Annotated[datetime, Depends(get_now)],
) -> dict[str, Any] | Response:
    result = await _resolve(gtin, session, off, cfg, settings, now, usda)  # LOOKUP-12
    if (not_modified := _cached(request, response, _etag(result, cfg))) is not None:
        return not_modified
    return {
        "gtin": result.product.gtin,
        "score": result.score,
        "explanation": explain(_rehydrate(result.score)),
        "attribution": ATTRIBUTION,
    }


@router.get("/{gtin}/alternatives")
async def get_alternatives(
    gtin: str,
    response: Response,
    session: Session,
    off: Annotated[OFFClient, Depends(get_off)],
    usda: Annotated[USDAClient | None, Depends(get_usda)],
    cfg: Annotated[ScoringConfig, Depends(default_config)],
    settings: Annotated[Settings, Depends(get_settings)],
    now: Annotated[datetime, Depends(get_now)],
) -> dict[str, Any]:
    result = await _resolve(gtin, session, off, cfg, settings, now, usda)  # ALT-1
    category, alternatives = await find_alternatives(session, result.product, result.score, cfg)
    response.headers["Cache-Control"] = CACHE_CONTROL  # ALT-9: no ETag, the list changes
    return {
        "gtin": result.product.gtin,
        "category": category,
        "alternatives": alternatives,
        "attribution": ATTRIBUTION,
    }  # ALT-7


@router.get("/{gtin}/recalls")
async def get_recalls(
    gtin: str,
    response: Response,
    session: Session,
    off: Annotated[OFFClient, Depends(get_off)],
    usda: Annotated[USDAClient | None, Depends(get_usda)],
    cfg: Annotated[ScoringConfig, Depends(default_config)],
    settings: Annotated[Settings, Depends(get_settings)],
    now: Annotated[datetime, Depends(get_now)],
) -> dict[str, Any]:
    result = await _resolve(gtin, session, off, cfg, settings, now, usda)  # RECALL-8
    response.headers["Cache-Control"] = "public, max-age=3600"  # RECALL-11: no ETag
    return {
        "gtin": result.product.gtin,
        "recalls": await find_recalls(session, result.product, cfg.recalls),
        "as_of": await recalls_as_of(session),
        "attribution": RECALL_ATTRIBUTION,
    }
