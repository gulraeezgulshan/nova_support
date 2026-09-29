"""Checkout stores the currency, rate and local amount, and starts the lifecycle."""

from collections.abc import Callable
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from database.models import FxRate, Order, User
from database.session import sync_session
from tests.fixtures.shop import place_order, shopper

pytestmark = pytest.mark.db


async def test_checkout_in_pkr_records_the_rate_and_rounded_amount(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    from datetime import UTC, datetime

    with sync_session() as db:
        db.add(FxRate(currency="PKR", rate=Decimal("281.4"), fetched_at=datetime.now(UTC)))
    order = await place_order(client, shopper(create_user, make_token), currency="PKR")
    assert (order["currency"], order["stage"], order["status"]) == ("PKR", "placed", "processing")
    assert Decimal(str(order["amount_local"])) == Decimal("78511")  # 279 x 281.4, whole rupees
    assert order["amount"] == 279.0 and order["next_step_at"] is not None
    with sync_session() as db:
        saved = db.scalars(select(Order).where(Order.order_ref == order["order_ref"])).one()
        assert [e.stage for e in saved.events] == ["placed"]


async def test_unknown_currency_is_refused(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    response = await client.post(
        "/api/v1/checkout",
        headers=shopper(create_user, make_token),
        json={"lines": [{"sku": "VH-AUD-P700", "quantity": 1}], "currency": "JPY"},
    )
    assert response.status_code == 422
