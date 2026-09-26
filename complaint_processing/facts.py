"""Build the rule-engine facts for a complaint from database records (never from the LLM)."""

from datetime import date, timedelta
from typing import Any

from complaint_rules.facts import FACTS
from database.models import Complaint, CustomerType, Order

REPEAT_WINDOW_DAYS = 60
REPEAT_MIN_GAP_HOURS = 24
CLOSED_STATUSES = {"resolved", "closed"}


def business_days_between(start: date, end: date) -> int:
    """Weekdays after `start` up to and including `end` (0 if end <= start)."""
    if end <= start:
        return 0
    days, current = 0, start
    while current < end:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days += 1
    return days


def order_facts(order: Order | None, today: date) -> dict[str, Any]:
    if order is None:
        return {"has_order": False}
    reference_date = order.delivered_date or today
    return {
        "has_order": True,
        "order_status": order.status,
        "order_amount": float(order.amount),
        "shipping_method": order.shipping_method,
        "days_since_order": (today - order.order_date).days,
        "days_since_delivery": (today - order.delivered_date).days
        if order.delivered_date
        else None,
        "days_late": business_days_between(order.committed_delivery_date, reference_date),
    }


def build_facts(
    complaint: Complaint, prior_complaints: list[Complaint], today: date
) -> dict[str, Any]:
    customer = complaint.customer
    window_start = today - timedelta(days=REPEAT_WINDOW_DAYS)
    # A resend within 24 hours is a duplicate submission, not a repeated complaint.
    recent = [
        c
        for c in prior_complaints
        if c.created_at.date() >= window_start
        and complaint.created_at - c.created_at >= timedelta(hours=REPEAT_MIN_GAP_HOURS)
    ]
    signals = complaint.signals or {}
    amounts = (complaint.entities or {}).get("amounts") or []

    facts: dict[str, Any] = {
        "customer_type": str(customer.customer_type),
        "is_vip": customer.customer_type == CustomerType.VIP,
        "repeat_count": len(recent),
        "unresolved_repeat_count": sum(c.status not in CLOSED_STATUSES for c in recent),
        "disputed_amount": max(amounts) if amounts else None,
        **order_facts(complaint.order, today),
    }
    for name, spec in FACTS.items():
        if spec.type == "bool" and name not in facts:
            facts[name] = bool(signals.get(name))
    return facts
