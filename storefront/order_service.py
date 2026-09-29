"""Customer and staff actions on orders: load, check, move, e-mail."""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Customer, Order, User
from storefront.config import storefront_config
from storefront.lifecycle import LifecycleError, move
from storefront.order_emails import queue_order_email


class OrderNotFound(LookupError):
    pass


async def load_order(db: AsyncSession, ref: str) -> Order | None:
    return await db.scalar(
        select(Order)
        .options(selectinload(Order.customer), selectinload(Order.events))
        .where(Order.order_ref == ref.upper())
    )


async def own_order(db: AsyncSession, user: User, ref: str) -> Order:
    order = await load_order(db, ref)
    customer = await db.scalar(select(Customer).where(Customer.user_id == user.id))
    if order is None or customer is None or order.customer_id != customer.id:
        raise OrderNotFound(ref)
    return order


async def customer_cancel(db: AsyncSession, user: User, ref: str) -> Order:
    order = await own_order(db, user, ref)
    move(db, order, "cancelled", "customer", user_id=user.id, note="Cancelled by the customer")
    queue_order_email(db, order, order.customer, "cancelled")
    await db.commit()
    return order


async def customer_return(db: AsyncSession, user: User, ref: str, reason: str) -> Order:
    order = await own_order(db, user, ref)
    window = storefront_config().returns.window_days
    delivered = order.delivered_date
    if order.stage == "delivered" and delivered and (date.today() - delivered).days > window:
        raise LifecycleError(f"Returns are accepted within {window} days of delivery.", order.stage)
    move(db, order, "return_requested", "customer", user_id=user.id, note=reason,
         now=datetime.now(UTC))  # fmt: skip
    await db.commit()
    return order
