"""Rates are stored, survive a failed refresh, fall back for PKR, and are public."""

from decimal import Decimal

import httpx
import pytest

from database.session import sync_session
from storefront.currency import current_rates, refresh_rates
from tests.fixtures.settings import use_settings

pytestmark = pytest.mark.db
OK = {"result": "success", "rates": {"PKR": 281.4, "EUR": 0.92, "GBP": 0.79, "AED": 3.67}}


def client(ok: bool) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json=OK) if ok else httpx.Response(503)))  # fmt: skip


def test_no_rates_yet_uses_the_pkr_fallback(clean_db: None) -> None:
    use_settings(orders={"fallback_pkr_rate": 300.0})
    with sync_session() as db:
        assert current_rates(db) == {"USD": Decimal("1"), "PKR": Decimal("300")}


def test_refresh_stores_and_a_failure_keeps_them(clean_db: None) -> None:
    assert refresh_rates(client(True)) == 4
    assert refresh_rates(client(False)) == 0
    with sync_session() as db:
        assert current_rates(db)["PKR"] == Decimal("281.4")


async def test_currency_endpoint_is_public(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/v1/currency")).json()
    assert body["rates"]["USD"] == 1 and "PKR" in body["rates"]
    assert {c["code"] for c in body["currencies"]} == {"USD", "PKR", "EUR", "GBP", "AED"}
