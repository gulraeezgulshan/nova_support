"""New order columns and events persist with sensible defaults."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from database.models import Customer, CustomerType, Order, OrderEvent
from database.session import sync_session

pytestmark = pytest.mark.db


def test_order_defaults_and_events(clean_db: None) -> None:
    with sync_session() as db:
        customer = Customer(
            customer_ref="CUST-990001", full_name="Ada", customer_type=CustomerType.STANDARD
        )
        db.add(customer)
        db.flush()
        order = Order(
            order_ref="ORD-990001", customer_id=customer.id, product_name="Pulse 700",
            product_category="audio", amount=Decimal("279.00"), order_date=date(2026, 9, 29),
            committed_delivery_date=date(2026, 10, 6),
        )  # fmt: skip
        db.add(order)
        db.flush()
        db.add(OrderEvent(order_id=order.id, stage="placed", actor="customer"))
    with sync_session() as db:
        order = db.scalars(select(Order).where(Order.order_ref == "ORD-990001")).one()
        assert (order.stage, order.currency, order.fx_rate, order.manual_hold) == (
            "placed", "USD", Decimal("1"), False,
        )  # fmt: skip
        assert order.emails_sent == [] and order.expected_delivery_date is None
        assert [e.stage for e in order.events] == ["placed"]
