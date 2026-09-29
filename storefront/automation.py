"""The courier simulation: due shop orders advance one step (run by the Settings tick)."""

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

import app_settings
from database.models import Order
from database.session import sync_session
from src.core.logging import get_logger
from storefront.lifecycle import FORWARD, MOVING, delay, move
from storefront.orders import add_business_days

log = get_logger(__name__)
BATCH = 50
DELAY_WAIT_STEPS = 3


def advance_due_orders(now: datetime | None = None, rng: random.Random | None = None) -> list[str]:
    cfg = app_settings.runtime().orders
    if not cfg.auto_advance:
        return []
    now, rng = now or datetime.now(UTC), rng or random.Random()  # noqa: S311 - a simulation, not security
    step = timedelta(minutes=cfg.step_minutes)
    moved: list[str] = []
    with sync_session() as db:
        orders = db.scalars(
            select(Order)
            .where(
                Order.checkout_ref.is_not(None),
                Order.stage.in_(MOVING),
                Order.manual_hold.is_(False),
                Order.next_step_at <= now,
            )
            .order_by(Order.next_step_at)
            .limit(BATCH)
            .with_for_update(skip_locked=True)  # overlapping ticks never move an order twice
        ).all()
        for order in orders:
            try:
                with db.begin_nested():
                    wait = step
                    if (order.stage == "shipped" and order.expected_delivery_date is None
                            and rng.random() * 100 < cfg.delay_chance_pct):  # fmt: skip
                        expected = add_business_days(
                            order.committed_delivery_date, rng.randint(2, 5)
                        )
                        delay(db, order, expected, "system", now=now)
                        wait = step * DELAY_WAIT_STEPS
                    target = FORWARD[order.stage]
                    if (
                        order.stage == "out_for_delivery"
                        and rng.random() * 100 < cfg.lost_chance_pct
                    ):
                        target = "lost"
                    move(db, order, target, "system", now=now)
                    if order.stage in MOVING:
                        order.next_step_at = now + wait
                moved.append(order.order_ref)
            except Exception:  # one broken order never stops the batch
                log.exception("orders.advance_failed", order=order.order_ref)
    return moved
