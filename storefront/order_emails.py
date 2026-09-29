"""E-mails to customers when their order moves (through the outbox, like complaint replies)."""

from functools import lru_cache
from typing import Any

import yaml
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import app_settings
from database.models import Customer, Order, OutboundEmail
from email_channel.outbound import queue
from src.core.config import ROOT_DIR
from storefront.currency import CURRENCIES

EMAIL_KINDS = (
    "placed",
    "shipped",
    "delayed",
    "delivered",
    "cancelled",
    "returned",
    "return_refused",
)


@lru_cache
def _texts() -> dict[str, dict[str, str]]:
    with (ROOT_DIR / "config" / "order_emails.yaml").open(encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle)
    return data


def format_amount(order: Order) -> str:
    code = order.currency if order.currency in CURRENCIES else "USD"
    amount = order.amount_local if order.amount_local is not None else order.amount
    c = CURRENCIES[code]
    return f"{c.symbol} {amount:,.{c.decimals}f}"


def queue_order_email(
    db: Session | AsyncSession, order: Order, customer: Customer, kind: str
) -> OutboundEmail | None:
    settings = app_settings.runtime()
    if kind not in EMAIL_KINDS or not settings.orders.emails or not customer.email:
        return None
    if kind in (order.emails_sent or []):
        return None
    when = (
        order.delivered_date
        if kind == "delivered"
        else (order.expected_delivery_date or order.committed_delivery_date)
    )
    values = {
        "name": customer.full_name.split(" ")[0] if customer.full_name else "there",
        "order_ref": order.order_ref,
        "product": order.product_name,
        "amount": format_amount(order),
        "date": f"{when:%d %b %Y}" if when else "",
        "shop": settings.branding.shop_name,
    }
    text = _texts()[kind]
    order.emails_sent = [*(order.emails_sent or []), kind]
    return queue(
        db,
        complaint_id=None,
        order_id=order.id,
        to=customer.email,
        kind=f"order_{kind}",
        subject=text["subject"].format(**values),
        body=text["body"].format(**values),
        in_reply_to=None,
        references=[],
    )
