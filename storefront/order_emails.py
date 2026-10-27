"""E-mails to customers when their order moves (through the outbox, like complaint replies)."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import app_settings
from app_settings.texts import render
from database.models import Customer, Order, OutboundEmail
from email_channel.outbound import queue
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
    text = settings.texts.order_emails[kind]  # Settings → Customer texts
    order.emails_sent = [*(order.emails_sent or []), kind]
    return queue(
        db,
        complaint_id=None,
        order_id=order.id,
        to=customer.email,
        kind=f"order_{kind}",
        subject=render(text.subject, **values),
        body=render(text.body, **values),
        in_reply_to=None,
        references=[],
    )
