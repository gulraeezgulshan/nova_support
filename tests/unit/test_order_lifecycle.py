"""Order stages: allowed moves, status mapping, history, delays never move the promise."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from database.models import Order
from storefront.lifecycle import STATUS_OF, LifecycleError, delay, deliver_late, move

NOW = datetime(2026, 9, 29, 10, 0, tzinfo=UTC)


class Db:
    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)


def order(stage: str = "placed", shop: bool = True) -> Order:
    return Order(
        order_ref="ORD-800100", stage=stage, status=STATUS_OF[stage],
        checkout_ref="CHK-1" if shop else None, product_name="Pulse 700",
        product_category="audio", amount=Decimal("279"), order_date=date(2026, 9, 21),
        committed_delivery_date=date(2026, 9, 28), emails_sent=[],
    )  # fmt: skip


def test_the_happy_path_and_status_mapping() -> None:
    o, db = order(), Db()
    for stage, status in [
        ("packed", "processing"),
        ("shipped", "shipped"),
        ("out_for_delivery", "shipped"),
        ("delivered", "delivered"),
    ]:
        move(db, o, stage, "system", now=NOW)
        assert (o.stage, o.status) == (stage, status)
    assert o.delivered_date == NOW.date() and o.next_step_at is None
    assert [e.stage for e in db.added] == ["packed", "shipped", "out_for_delivery", "delivered"]


@pytest.mark.parametrize(
    ("start", "to"),
    [
        ("placed", "shipped"),
        ("shipped", "cancelled"),
        ("delivered", "packed"),
        ("returned", "return_requested"),
    ],
)
def test_illegal_moves_are_refused(start: str, to: str) -> None:
    with pytest.raises(LifecycleError):
        move(Db(), order(start), to, "staff", now=NOW)


def test_dataset_orders_never_move() -> None:
    with pytest.raises(LifecycleError):
        move(Db(), order("placed", shop=False), "packed", "system", now=NOW)


def test_a_delay_sets_the_expected_date_and_keeps_the_promise() -> None:
    o, db = order("shipped"), Db()
    delay(db, o, date(2026, 10, 2), "system", now=NOW)
    assert o.committed_delivery_date == date(2026, 9, 28)  # the promise
    assert o.expected_delivery_date == date(2026, 10, 2)
    assert db.added[-1].stage == "delayed"
    with pytest.raises(LifecycleError):
        delay(Db(), order("placed"), date(2026, 10, 2), "system", now=NOW)


def test_late_delivery_shifts_the_timeline() -> None:
    o, db = order("out_for_delivery"), Db()
    deliver_late(db, o, 3, user_id=None, now=NOW)
    assert o.stage == "delivered" and o.delivered_date == NOW.date()
    assert o.committed_delivery_date == date(2026, 9, 24)  # 3 business days before Tue 29 Sep
    assert "3 business days late" in (db.added[-1].note or "")
