"""The courier simulation: only due, not-held shop orders move; seeded delays and losses."""

import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update

from database.models import Order, User
from database.session import sync_session
from storefront.automation import advance_due_orders
from tests.fixtures.settings import use_settings
from tests.fixtures.shop import place_order, shopper

pytestmark = pytest.mark.db
LATER = datetime.now(UTC) + timedelta(hours=1)


def stage(ref: str) -> str:
    with sync_session() as db:
        return db.scalars(select(Order.stage).where(Order.order_ref == ref)).one()


async def test_due_orders_move_one_step(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    use_settings(orders={"delay_chance_pct": 0, "lost_chance_pct": 0})
    ref = (await place_order(client, shopper(create_user, make_token)))["order_ref"]
    assert advance_due_orders(datetime.now(UTC)) == []  # not due yet
    assert advance_due_orders(LATER) == [ref] and stage(ref) == "packed"
    assert advance_due_orders(LATER) == []  # next step is step_minutes after LATER


async def test_held_orders_and_switched_off_automation_do_not_move(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    ref = (await place_order(client, shopper(create_user, make_token)))["order_ref"]
    with sync_session() as db:
        db.execute(update(Order).where(Order.order_ref == ref).values(manual_hold=True))
    assert advance_due_orders(LATER) == []
    with sync_session() as db:
        db.execute(update(Order).where(Order.order_ref == ref).values(manual_hold=False))
    use_settings(orders={"auto_advance": False})
    assert advance_due_orders(LATER) == []


async def test_seeded_delay_then_delivery(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    use_settings(orders={"delay_chance_pct": 100, "lost_chance_pct": 0, "step_minutes": 1})
    ref = (await place_order(client, shopper(create_user, make_token)))["order_ref"]
    now = LATER
    for _ in range(12):
        advance_due_orders(now, random.Random(1))  # noqa: S311 - seeded simulation
        now += timedelta(minutes=5)
    with sync_session() as db:
        order = db.scalars(select(Order).where(Order.order_ref == ref)).one()
        assert order.stage == "delivered" and order.expected_delivery_date is not None
        assert "delayed" in [e.stage for e in order.events]
