"""Order e-mails: one per order and kind, only with an address and when switched on."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from database.models import OutboundEmail, User
from database.session import sync_session
from storefront.automation import advance_due_orders
from tests.fixtures.settings import use_settings
from tests.fixtures.shop import place_order, shopper

pytestmark = pytest.mark.db


def kinds() -> list[str]:
    with sync_session() as db:
        return [
            e.kind for e in db.scalars(select(OutboundEmail).order_by(OutboundEmail.created_at))
        ]


async def test_placed_and_shipped_emails_once(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    use_settings(orders={"delay_chance_pct": 0})
    order = await place_order(client, shopper(create_user, make_token), currency="PKR")
    now = datetime.now(UTC) + timedelta(hours=1)
    for _ in range(2):
        advance_due_orders(now)
        now += timedelta(minutes=5)
    assert kinds() == ["order_placed", "order_shipped"]
    with sync_session() as db:
        placed = db.scalars(select(OutboundEmail).where(OutboundEmail.kind == "order_placed")).one()
        assert order["order_ref"] in placed.subject and "Rs" in placed.body
        assert placed.to_address == "shopper@example.test" and placed.order_id is not None


async def test_switched_off_means_no_order_emails(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    use_settings(orders={"emails": False})
    await place_order(client, shopper(create_user, make_token))
    assert kinds() == []
