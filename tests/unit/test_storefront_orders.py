"""Delivery dates and demo delivery outcomes (no database)."""

from datetime import date

from storefront.orders import add_business_days, delivery_due

FRIDAY = date(2026, 9, 25)


def test_business_days_skip_weekends() -> None:
    assert add_business_days(FRIDAY, 1) == date(2026, 9, 28)  # Monday
    assert add_business_days(FRIDAY, 3) == date(2026, 9, 30)
    assert add_business_days(FRIDAY, 0) == FRIDAY


def test_delivery_due_by_shipping_method() -> None:
    assert delivery_due(FRIDAY, "standard") == date(2026, 10, 2)  # 5 business days
    assert delivery_due(FRIDAY, "express") == date(2026, 9, 29)  # 2 business days
