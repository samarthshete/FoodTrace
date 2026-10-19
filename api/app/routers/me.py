"""The signed-in user's account: profile, preferences, history, favorites (specs/018).

Every per-user query runs inside `as_user`, which switches the transaction to the `ofs_app`
role (no BYPASSRLS) and sets `app.user_id`. The row-level security policies from migration
0006 then decide which rows exist, so one user can never see another's rows (ACC-14).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import UserId
from app.problems import Problem
from app.routers.products import Session, get_now
from app.scoring.config import ScoringConfig, default_config
from app.services.gtin import InvalidGTIN, normalize

router = APIRouter(prefix="/me", tags=["me"])
Allergen = Literal["milk", "eggs", "fish", "crustacean_shellfish", "tree_nuts", "peanuts",
                   "wheat", "soybeans", "sesame"]  # fmt: skip
Diet = Literal["vegan", "vegetarian", "gluten_free"]
DEDUPE = timedelta(minutes=10)  # ACC-9
HISTORY_CAP = 1000  # ACC-17
PAGE = 50  # ACC-10
Config = Annotated[ScoringConfig, Depends(default_config)]


class PreferencesIn(BaseModel):  # ACC-5
    model_config = ConfigDict(extra="forbid")
    allergens: list[Allergen] = []
    diets: list[Diet] = []
    save_history: bool = True


class ScanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gtin: str


@asynccontextmanager
async def as_user(session: AsyncSession, user_id: str) -> AsyncIterator[AsyncSession]:
    """One transaction held to the row-level security policies for this user (ACC-14)."""
    async with session.begin():
        await session.execute(text("SET LOCAL ROLE ofs_app"))
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id}
        )
        yield session


def _gtin(raw: str) -> str:
    try:
        return normalize(raw)
    except InvalidGTIN as exc:
        raise Problem(422, "Invalid barcode", str(exc)) from exc


async def _preferences(session: AsyncSession) -> dict[str, Any]:
    row = (await session.execute(text(
        "SELECT allergens, diets, save_history FROM user_preferences"
    ))).first()  # fmt: skip
    if row is None:  # defaults until the user saves preferences (ACC-5)
        return {"allergens": [], "diets": [], "save_history": True}
    return {"allergens": row.allergens, "diets": row.diets, "save_history": row.save_history}


def _band(band_id: str | None, cfg: ScoringConfig) -> dict[str, str] | None:
    return next(({"id": b.id, "label": b.label} for b in cfg.bands if b.id == band_id), None)


@router.get("")
async def me(user_id: UserId, session: Session) -> dict[str, Any]:  # ACC-5
    async with session.begin():
        user = (await session.execute(
            text('SELECT name, email, image FROM "user" WHERE id = :id'), {"id": user_id}
        )).first()  # fmt: skip
    if user is None:
        raise Problem(401, "Sign in required", "This account no longer exists.")
    async with as_user(session, user_id):
        prefs = await _preferences(session)
    return {"id": user_id, "name": user.name, "email": user.email, "image": user.image,
            "preferences": prefs}  # fmt: skip


@router.put("/preferences")
async def set_preferences(body: PreferencesIn, user_id: UserId, session: Session) -> dict[str, Any]:
    prefs = {"allergens": sorted(set(body.allergens)), "diets": sorted(set(body.diets)),
             "save_history": body.save_history}  # fmt: skip
    async with as_user(session, user_id):
        await session.execute(text("""
            INSERT INTO user_preferences (user_id, allergens, diets, save_history, updated_at)
            VALUES (:uid, :allergens, :diets, :save_history, now())
            ON CONFLICT (user_id) DO UPDATE SET allergens = EXCLUDED.allergens,
              diets = EXCLUDED.diets, save_history = EXCLUDED.save_history, updated_at = now()
        """), {"uid": user_id, **prefs})  # fmt: skip
    return prefs


@router.post("/history", status_code=201)
async def record_scan(
    body: ScanIn, user_id: UserId, session: Session, cfg: Config, response: Response,
    now: Annotated[datetime, Depends(get_now)],
) -> dict[str, Any]:  # fmt: skip
    """Save a product view to history (ACC-9), keeping the newest 1,000 (ACC-17)."""
    gtin = _gtin(body.gtin)
    async with as_user(session, user_id):
        if not (await _preferences(session))["save_history"]:
            response.status_code = 200
            return {"saved": False, "reason": "paused"}
        recent = await session.scalar(text(
            "SELECT 1 FROM scan_history WHERE gtin = :gtin AND scanned_at > :since LIMIT 1"
        ), {"gtin": gtin, "since": now - DEDUPE})  # fmt: skip
        if recent:
            response.status_code = 200
            return {"saved": False, "reason": "recent"}
        score = (await session.execute(text(
            "SELECT total, breakdown -> 'band' ->> 'id' AS band FROM scores "
            "WHERE gtin = :gtin AND engine_version = :v"
        ), {"gtin": gtin, "v": cfg.engine_version})).first()  # fmt: skip
        exists = await session.scalar(text("SELECT 1 FROM products WHERE gtin = :g"), {"g": gtin})
        if not exists:
            raise Problem(404, "Product not found", "Open the product before saving it.")
        new_id = await session.scalar(text("""
            INSERT INTO scan_history (user_id, gtin, scanned_at, total, band)
            VALUES (:uid, :gtin, :now, :total, :band) RETURNING id
        """), {"uid": user_id, "gtin": gtin, "now": now, "total": score.total if score else None,
               "band": score.band if score else None})  # fmt: skip
        await session.execute(text(
            "DELETE FROM scan_history WHERE id NOT IN "
            "(SELECT id FROM scan_history ORDER BY id DESC LIMIT :cap)"
        ), {"cap": HISTORY_CAP})  # fmt: skip
    return {"saved": True, "id": new_id}


@router.get("/history")
async def history(
    user_id: UserId, session: Session, cfg: Config,
    cursor: Annotated[int | None, Query()] = None,
) -> dict[str, Any]:  # fmt: skip
    """The user's scans, newest first, 50 per page (ACC-10)."""
    async with as_user(session, user_id):
        rows = (await session.execute(text("""
            SELECT h.id, h.gtin, h.scanned_at, h.total, h.band, p.name, p.brand, p.image_url
            FROM scan_history h JOIN products p ON p.gtin = h.gtin
            WHERE (CAST(:cursor AS BIGINT) IS NULL OR h.id < :cursor)
            ORDER BY h.id DESC LIMIT :n
        """), {"cursor": cursor, "n": PAGE + 1})).all()  # fmt: skip
    page = rows[:PAGE]
    items = [{"id": r.id, "gtin": r.gtin, "scanned_at": r.scanned_at.isoformat(),
              "name": r.name, "brand": r.brand, "image_url": r.image_url, "total": r.total,
              "band": _band(r.band, cfg)} for r in page]  # fmt: skip
    return {"items": items, "next_cursor": page[-1].id if len(rows) > PAGE else None}


@router.delete("/history/{scan_id}", status_code=204)
async def delete_scan(scan_id: int, user_id: UserId, session: Session) -> None:  # ACC-11
    async with as_user(session, user_id):
        result = await session.execute(text("DELETE FROM scan_history WHERE id = :id"),
                                       {"id": scan_id})  # fmt: skip
    if result.rowcount == 0:  # type: ignore[attr-defined]  # someone else's row looks absent (ACC-14)
        raise Problem(404, "Not found", "That scan isn't in your history.")


@router.delete("/history")
async def clear_history(user_id: UserId, session: Session) -> dict[str, int]:  # ACC-11
    async with as_user(session, user_id):
        result = await session.execute(text("DELETE FROM scan_history"))
    return {"deleted": result.rowcount}  # type: ignore[attr-defined]


@router.put("/favorites/{gtin}", status_code=204)
async def add_favorite(gtin: str, user_id: UserId, session: Session) -> None:  # ACC-12
    code = _gtin(gtin)
    async with as_user(session, user_id):
        if not await session.scalar(text("SELECT 1 FROM products WHERE gtin = :g"), {"g": code}):
            raise Problem(404, "Product not found", "Open the product before saving it.")
        await session.execute(text(
            "INSERT INTO favorites (user_id, gtin) VALUES (:uid, :g) ON CONFLICT DO NOTHING"
        ), {"uid": user_id, "g": code})  # fmt: skip


@router.delete("/favorites/{gtin}", status_code=204)
async def remove_favorite(gtin: str, user_id: UserId, session: Session) -> None:  # ACC-12
    async with as_user(session, user_id):
        await session.execute(text("DELETE FROM favorites WHERE gtin = :g"), {"g": _gtin(gtin)})


@router.get("/favorites")
async def favorites(user_id: UserId, session: Session, cfg: Config) -> dict[str, Any]:  # ACC-12
    async with as_user(session, user_id):
        rows = (await session.execute(text("""
            SELECT f.gtin, p.name, p.brand, p.image_url, s.total,
                   s.breakdown -> 'band' ->> 'id' AS band
            FROM favorites f JOIN products p ON p.gtin = f.gtin
            LEFT JOIN scores s ON s.gtin = f.gtin AND s.engine_version = :v
            ORDER BY f.created_at DESC
        """), {"v": cfg.engine_version})).all()  # fmt: skip
    return {"items": [{"gtin": r.gtin, "name": r.name, "brand": r.brand,
                       "image_url": r.image_url, "total": r.total, "band": _band(r.band, cfg)}
                      for r in rows]}  # fmt: skip


@router.get("/contributions")
async def my_contributions(user_id: UserId, session: Session) -> dict[str, Any]:  # ACC-18
    async with session.begin():
        rows = (await session.execute(text(
            "SELECT gtin, extracted ->> 'name' AS name, created_at FROM contributions "
            "WHERE user_id = :uid ORDER BY created_at DESC"
        ), {"uid": user_id})).all()  # fmt: skip
    return {"items": [{"gtin": r.gtin, "name": r.name, "created_at": r.created_at.isoformat()}
                      for r in rows]}  # fmt: skip


@router.delete("", status_code=204)
async def delete_account(user_id: UserId, session: Session) -> None:
    """Delete the user and everything of theirs in one transaction (ACC-13). Sessions,
    accounts, preferences, history and favorites cascade; contributions are unlinked."""
    async with session.begin():
        await session.execute(text('DELETE FROM "user" WHERE id = :id'), {"id": user_id})
