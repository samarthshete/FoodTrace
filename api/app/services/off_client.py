"""Open Food Facts live product API client (specs/006, LOOKUP-3..5).

Good-citizen rules: descriptive User-Agent, only the fields we need, back off on 429/503.
"""

import asyncio
from typing import Any

import httpx

FIELDS = ",".join([
    "code", "product_name", "product_name_en", "brands", "categories_tags", "image_front_url",
    "ingredients_text", "ingredients_text_en", "nutriments", "nova_group", "labels_tags",
    "additives_tags", "allergens_tags", "traces_tags", "ingredients_analysis_tags",
])  # fmt: skip
RETRY_STATUSES = {429, 503}
MAX_RETRIES = 2
MAX_RETRY_AFTER_S = 5.0


class SourceUnavailable(Exception):
    """OFF could not be reached or kept rate-limiting us."""


def _retry_delay(resp: httpx.Response, attempt: int) -> float:
    try:
        delay = float(str(resp.headers["Retry-After"]))
        return min(delay, MAX_RETRY_AFTER_S)
    except (KeyError, ValueError):
        return min(0.5 * 2.0**attempt, MAX_RETRY_AFTER_S)


class OFFClient:
    def __init__(self, http: httpx.AsyncClient, base_url: str, user_agent: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")
        self._headers = {"User-Agent": user_agent}

    async def _get(self, code: str) -> httpx.Response:
        url = f"{self._base}/api/v2/product/{code}.json"
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._http.get(url, params={"fields": FIELDS}, headers=self._headers)
            except httpx.HTTPError as exc:
                raise SourceUnavailable(str(exc)) from exc
            if resp.status_code not in RETRY_STATUSES:
                return resp
            if attempt < MAX_RETRIES:
                await asyncio.sleep(_retry_delay(resp, attempt))
        raise SourceUnavailable(f"OFF kept answering {resp.status_code}")

    async def fetch(self, codes: list[str]) -> dict[str, Any] | None:
        """Try each code form in order; return the first product found, else None."""
        for code in codes:
            resp = await self._get(code)
            if resp.status_code == 404:
                continue
            if resp.status_code >= 400:
                raise SourceUnavailable(f"OFF answered {resp.status_code}")
            body = resp.json()
            if body.get("status") == 1 and isinstance(body.get("product"), dict):
                product: dict[str, Any] = body["product"]
                return product
        return None


WRITE_PATH = "/cgi/product_jqm2.pl"


async def share_product(
    http: httpx.AsyncClient, base_url: str, user_agent: str, user: str, password: str,
    fields: dict[str, str],
) -> str:  # fmt: skip
    """Add a product to Open Food Facts (CONTRIB-10). Returns "ok" or a short error."""
    data = {"user_id": user, "password": password, **fields}
    try:
        resp = await http.post(f"{base_url.rstrip('/')}{WRITE_PATH}", data=data,
                               headers={"User-Agent": user_agent}, timeout=10)  # fmt: skip
        resp.raise_for_status()
        body = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        return f"error: {exc.__class__.__name__}"
    return "ok" if body.get("status") == 1 else f"error: {body.get('status_verbose', 'rejected')}"
