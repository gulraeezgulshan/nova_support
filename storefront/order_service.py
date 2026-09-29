"""Customer and staff actions on orders: load, check, move, e-mail."""

from datetime import UTC, date, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Customer, Order, User
from storefront.config import storefront_config
from storefront.lifecycle import FORWARD, LifecycleError, delay, deliver_late, move
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
    move(
        db,
        order,
        "return_requested",
        "customer",
        user_id=user.id,
        note=reason,
        now=datetime.now(UTC),
    )
    await db.commit()
    return order


ACTIONS = ("advance", "delay", "lose", "cancel", "approve_return", "refuse_return", "resume_auto")


async def list_orders(
    db: AsyncSession,
    *,
    stage: str | None = None,
    q: str | None = None,
    needs_action: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[Order]:
    stmt = (
        select(Order)
        .join(Customer)
        .options(selectinload(Order.customer))
        .where(Order.checkout_ref.is_not(None))
    )
    if stage:
        stmt = stmt.where(Order.stage == stage)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Order.order_ref.ilike(like),
                Order.product_name.ilike(like),
                Customer.full_name.ilike(like),
                Customer.email.ilike(like),
            )
        )
    if needs_action:
        stmt = stmt.where(
            or_(
                Order.stage == "return_requested",
                (Order.expected_delivery_date.is_not(None))
                & (Order.stage.in_(("shipped", "out_for_delivery"))),
            )
        )
    stmt = stmt.order_by(Order.created_at.desc()).limit(min(limit, 100)).offset(offset)
    return list((await db.scalars(stmt)).all())


async def staff_action(
    db: AsyncSession,
    user: User,
    ref: str,
    action: str,
    *,
    note: str | None = None,
    new_date: date | None = None,
    days_late: int = 0,
) -> Order:
    order = await load_order(db, ref)
    if order is None:
        raise OrderNotFound(ref)
    customer = order.customer
    if action == "resume_auto":
        order.manual_hold = False
        order.next_step_at = datetime.now(UTC)
    elif action == "delay":
        if new_date is None:
            raise LifecycleError("Give the new expected date.", order.stage)
        delay(db, order, new_date, "staff", user_id=user.id, note=note)
        queue_order_email(db, order, customer, "delayed")
    elif action == "advance" and order.stage == "out_for_delivery" and days_late > 0:
        deliver_late(db, order, days_late, user_id=user.id)
        queue_order_email(db, order, customer, "delivered")
    else:
        to = {
            "advance": FORWARD.get(order.stage, "?"),
            "lose": "lost",
            "cancel": "cancelled",
            "approve_return": "returned",
            "refuse_return": "return_refused",
        }[action]
        move(db, order, to, "staff", user_id=user.id, note=note)
        queue_order_email(db, order, customer, to)
    if action != "resume_auto":
        order.manual_hold = True
    await db.commit()
    return order
