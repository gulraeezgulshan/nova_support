"""The only place an order's stage changes: allowed moves, status mapping and history."""

import uuid
from datetime import UTC, date, datetime
from typing import Literal, Protocol

from database.models import Order, OrderEvent
from storefront.orders import SHIPPING_DAYS, subtract_business_days

STAGES = (
    "placed", "packed", "shipped", "out_for_delivery", "delivered",
    "lost", "cancelled", "return_requested", "return_refused", "returned",
)  # fmt: skip
STATUS_OF = {
    "placed": "processing", "packed": "processing", "shipped": "shipped",
    "out_for_delivery": "shipped", "delivered": "delivered", "lost": "lost",
    "cancelled": "cancelled", "return_requested": "delivered",
    "return_refused": "delivered", "returned": "returned",
}  # fmt: skip
FORWARD = {"placed": "packed", "packed": "shipped", "shipped": "out_for_delivery",
           "out_for_delivery": "delivered"}  # fmt: skip
ALLOWED: dict[str, set[str]] = {
    "placed": {"packed", "cancelled"},
    "packed": {"shipped", "cancelled"},
    "shipped": {"out_for_delivery", "lost"},
    "out_for_delivery": {"delivered", "lost"},
    "delivered": {"return_requested"},
    "return_requested": {"returned", "return_refused"},
}
MOVING = ("placed", "packed", "shipped", "out_for_delivery")
LABELS = {s: s.replace("_", " ") for s in STAGES}
Actor = Literal["system", "staff", "customer"]


class Adder(Protocol):
    def add(self, instance: object) -> None: ...


class LifecycleError(ValueError):
    def __init__(self, message: str, stage: str):
        super().__init__(message)
        self.stage = stage


def _event(db: Adder, order: Order, stage: str, actor: Actor, user_id: uuid.UUID | None,
           note: str | None, now: datetime) -> OrderEvent:  # fmt: skip
    event = OrderEvent(order_id=order.id, stage=stage, note=note, actor=actor,
                       actor_user_id=user_id, created_at=now)  # fmt: skip
    db.add(event)
    return event


def move(
    db: Adder, order: Order, to: str, actor: Actor, *,
    user_id: uuid.UUID | None = None, note: str | None = None, now: datetime | None = None,
) -> OrderEvent:  # fmt: skip
    if order.checkout_ref is None:
        raise LifecycleError("Only orders placed in the shop move.", order.stage)
    if to not in ALLOWED.get(order.stage, set()):
        raise LifecycleError(
            f"An order that is {LABELS[order.stage]} cannot become {LABELS.get(to, to)}.",
            order.stage,
        )
    now = now or datetime.now(UTC)
    order.stage, order.status = to, STATUS_OF[to]
    if to == "delivered":
        order.delivered_date = now.date()
    if to not in MOVING:
        order.next_step_at = None
    return _event(db, order, to, actor, user_id, note, now)


def delay(
    db: Adder, order: Order, expected: date, actor: Actor, *,
    user_id: uuid.UUID | None = None, note: str | None = None, now: datetime | None = None,
) -> OrderEvent:  # fmt: skip
    if order.stage not in ("shipped", "out_for_delivery"):
        raise LifecycleError("Only orders on their way can be delayed.", order.stage)
    if expected <= order.committed_delivery_date:
        raise LifecycleError("The new date must be after the promised date.", order.stage)
    order.expected_delivery_date = expected
    text = f"Delayed: now expected {expected:%d %b %Y}" + (f". {note}" if note else "")
    return _event(db, order, "delayed", actor, user_id, text, now or datetime.now(UTC))


def deliver_late(
    db: Adder, order: Order, days_late: int, *, user_id: uuid.UUID | None,
    now: datetime | None = None,
) -> OrderEvent:  # fmt: skip
    """Demo timeline: promised `days_late` business days before today, delivered today."""
    now = now or datetime.now(UTC)
    promised = subtract_business_days(now.date(), days_late)
    order.committed_delivery_date = promised
    order.order_date = subtract_business_days(promised, SHIPPING_DAYS.get(order.shipping_method, 5))
    note = f"Delivered {days_late} business day{'s' if days_late != 1 else ''} late (demo timeline)"
    return move(db, order, "delivered", "staff", user_id=user_id, note=note, now=now)
