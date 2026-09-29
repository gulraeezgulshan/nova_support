"""Checkout (one order per cart line, server-side prices) and demo delivery outcomes."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app_settings
from complaint_processing.service import next_ref
from database.models import CHECKOUT_REF_SEQ, ORDER_REF_SEQ, Customer, Order, OrderEvent, Product
from storefront.config import storefront_config
from storefront.currency import to_local
from storefront.order_emails import queue_order_email

SHIPPING_DAYS = {  # DEL-POL-04, via config/storefront.yaml
    "standard": storefront_config().shipping.standard_days,
    "express": storefront_config().shipping.express_days,
}
OUTCOMES = {"on_time", "late", "lost", "damaged"}
MAX_LINES, MAX_QUANTITY = 10, 5


def add_business_days(start: date, days: int) -> date:
    current, added = start, 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def subtract_business_days(end: date, days: int) -> date:
    current, removed = end, 0
    while removed < days:
        current -= timedelta(days=1)
        if current.weekday() < 5:
            removed += 1
    return current


def delivery_due(order_date: date, shipping_method: str) -> date:
    return add_business_days(order_date, SHIPPING_DAYS[shipping_method])


@dataclass(frozen=True)
class CheckoutLine:
    sku: str
    quantity: int


class CheckoutError(ValueError):
    def __init__(self, issues: list[str]):
        super().__init__("; ".join(issues))
        self.issues = issues


async def checkout(
    db: AsyncSession,
    customer: Customer,
    lines: list[CheckoutLine],
    shipping_method: str,
    today: date,
    *,
    currency: str = "USD",
    rates: dict[str, Decimal] | None = None,
    now: datetime | None = None,
) -> list[Order]:
    issues: list[str] = []
    if not 1 <= len(lines) <= MAX_LINES:
        issues.append(f"A checkout needs 1 to {MAX_LINES} lines.")
    if shipping_method not in SHIPPING_DAYS:
        issues.append(f"Unknown shipping method '{shipping_method}'.")
    skus = [line.sku for line in lines]
    products = {
        p.sku: p
        for p in await db.scalars(select(Product).where(Product.sku.in_(skus), Product.is_active))
    }
    for line in lines:
        if line.sku not in products:
            issues.append(f"Product {line.sku} is not available.")
        if not 1 <= line.quantity <= MAX_QUANTITY:
            issues.append(f"Quantity for {line.sku} must be 1 to {MAX_QUANTITY}.")
    if issues:
        raise CheckoutError(issues)

    rates = rates or {"USD": Decimal("1")}
    if currency not in rates:
        currency = "USD"  # no rate yet: charge and show in USD
    rate = rates[currency]
    now = now or datetime.now(UTC)
    step = timedelta(minutes=app_settings.runtime().orders.step_minutes)
    checkout_ref = await next_ref(db, "CHK", CHECKOUT_REF_SEQ)
    due = delivery_due(today, shipping_method)
    orders = []
    for line in lines:
        product = products[line.sku]
        order = Order(
            order_ref=await next_ref(db, "ORD", ORDER_REF_SEQ),
            transaction_ref=f"TXN-{uuid.uuid4().hex[:10].upper()}",
            customer_id=customer.id,
            product_id=product.id,
            product_name=product.name,
            product_category=product.product_line,
            quantity=line.quantity,
            amount=product.price * line.quantity,
            shipping_method=shipping_method,
            order_date=today,
            committed_delivery_date=due,
            delivered_date=None,
            status="processing",
            checkout_ref=checkout_ref,
            stage="placed",
            currency=currency,
            fx_rate=rate,
            amount_local=to_local(product.price * line.quantity, rate, currency),
            next_step_at=now + step,
        )
        db.add(order)
        orders.append(order)
    await db.flush()
    for order in orders:
        db.add(OrderEvent(order_id=order.id, stage="placed", actor="customer", created_at=now))
        queue_order_email(db, order, customer, "placed")
    await db.flush()
    return orders


def simulate(order: Order, outcome: str, days: int, today: date) -> None:
    """Rewrite the order's timeline so the outcome has just happened (demo only)."""
    if outcome not in OUTCOMES:
        raise ValueError(f"Unknown outcome '{outcome}'.")
    transit = SHIPPING_DAYS.get(order.shipping_method, 3)
    if outcome == "lost":
        committed = subtract_business_days(today, 4)
        delivered, status = None, "lost"
    else:
        delivered = subtract_business_days(today, 1)
        committed = subtract_business_days(delivered, days if outcome == "late" else 0)
        status = "delivered"
    order.committed_delivery_date = committed
    order.order_date = subtract_business_days(committed, transit)
    order.delivered_date = delivered
    order.status = status
