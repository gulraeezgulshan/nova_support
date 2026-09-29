"""Local currencies: prices stay USD; visitors see their currency at the day's rate."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import app_settings
from database.models import FxRate
from database.session import sync_session
from src.core.logging import get_logger

log = get_logger(__name__)
RATES_URL = "https://open.er-api.com/v6/latest/USD"


@dataclass(frozen=True)
class Currency:
    code: str
    symbol: str
    decimals: int


CURRENCIES = {
    "USD": Currency("USD", "$", 2),
    "PKR": Currency("PKR", "Rs", 0),
    "EUR": Currency("EUR", "€", 2),
    "GBP": Currency("GBP", "£", 2),
    "AED": Currency("AED", "AED", 2),
}


class RatesError(RuntimeError):
    pass


def to_local(usd: Decimal, rate: Decimal, code: str) -> Decimal:
    places = Decimal(1).scaleb(-CURRENCIES[code].decimals)
    return (usd * rate).quantize(places, rounding=ROUND_HALF_UP)


def fetch_rates(client: httpx.Client | None = None) -> dict[str, Decimal]:
    http = client or httpx.Client(timeout=10)
    try:
        response = http.get(RATES_URL)
        body = response.json() if response.status_code == 200 else {}
    except (httpx.HTTPError, ValueError) as exc:
        raise RatesError(str(exc)) from exc
    if body.get("result") != "success":
        raise RatesError(f"rates service answered {response.status_code}")
    rates = body.get("rates") or {}
    return {code: Decimal(str(rates[code])) for code in CURRENCIES if code in rates}


def refresh_rates(client: httpx.Client | None = None, now: datetime | None = None) -> int:
    """Store the day's rates; on failure keep the last ones. Returns how many were stored."""
    try:
        rates = fetch_rates(client)
    except RatesError as exc:
        log.warning("fx.refresh_failed", error=str(exc))
        return 0
    now = now or datetime.now(UTC)
    rows = [{"currency": c, "rate": r, "fetched_at": now} for c, r in rates.items() if c != "USD"]
    with sync_session() as db:
        for row in rows:
            db.execute(
                insert(FxRate)
                .values(**row)
                .on_conflict_do_update(
                    index_elements=[FxRate.currency],
                    set_={"rate": row["rate"], "fetched_at": now},
                )
            )
    return len(rows)


def _with_fallback(stored: dict[str, Decimal]) -> dict[str, Decimal]:
    rates = {"USD": Decimal("1"), **stored}
    if "PKR" not in rates:
        rates["PKR"] = Decimal(str(app_settings.runtime().orders.fallback_pkr_rate))
    return rates


def current_rates(db: Session) -> dict[str, Decimal]:
    return _with_fallback({r.currency: r.rate for r in db.scalars(select(FxRate))})


async def current_rates_async(db: AsyncSession) -> dict[str, Decimal]:
    return _with_fallback({r.currency: r.rate for r in await db.scalars(select(FxRate))})
