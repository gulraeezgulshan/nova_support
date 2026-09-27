"""Delivery dates and demo delivery outcomes (no database)."""

from datetime import date
from decimal import Decimal

import pytest

from complaint_processing.facts import business_days_between
from database.models import Order
from storefront.orders import add_business_days, delivery_due, simulate

FRIDAY = date(2026, 9, 25)


def test_business_days_skip_weekends() -> None:
    assert add_business_days(FRIDAY, 1) == date(2026, 9, 28)  # Monday
    assert add_business_days(FRIDAY, 3) == date(2026, 9, 30)
    assert add_business_days(FRIDAY, 0) == FRIDAY


def test_delivery_due_by_shipping_method() -> None:
    assert delivery_due(FRIDAY, "standard") == date(2026, 10, 2)  # 5 business days
    assert delivery_due(FRIDAY, "express") == date(2026, 9, 29)  # 2 business days


def order() -> Order:
    return Order(
        order_ref="ORD-800001",
        product_name="Nova X5 smartphone",
        product_category="SMARTPHONE",
        amount=Decimal("749.00"),
        shipping_method="standard",
        order_date=FRIDAY,
        committed_delivery_date=date(2026, 9, 30),
        status="processing",
    )


@pytest.mark.parametrize(
    ("outcome", "days", "status", "late"),
    [
        ("on_time", 0, "delivered", 0),
        ("late", 4, "delivered", 4),
        ("damaged", 0, "delivered", 0),
        ("lost", 0, "lost", None),
    ],
)
def test_simulate_rewrites_the_timeline_relative_to_today(
    outcome: str, days: int, status: str, late: int | None
) -> None:
    o = order()
    today = date(2026, 10, 15)
    simulate(o, outcome, days, today)
    assert o.status == status and o.order_date < o.committed_delivery_date
    if late is None:
        assert o.delivered_date is None and o.committed_delivery_date < today
    else:
        assert o.delivered_date is not None and o.delivered_date <= today
        assert business_days_between(o.committed_delivery_date, o.delivered_date) == late


def test_simulate_rejects_unknown_outcomes() -> None:
    with pytest.raises(ValueError):
        simulate(order(), "teleported", 0, FRIDAY)
