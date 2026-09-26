"""Trend detection (SRS Step 65): rising categories (e.g. delivery, billing), recurring
product issues, repeated service failures and escalation spikes.

The latest window (default 7 days) is compared with the window before it. Thresholds live in
`config/analytics.yaml` so they can be tuned without code changes.
"""

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, literal
from sqlalchemy.orm import Session

from database.models import Complaint
from src.analytics.filters import Filters
from src.analytics.metrics import IS_ESCALATED, IS_REPEAT, PRODUCT, labels, scoped
from src.core.domain import analytics_config


@dataclass
class Trend:
    # rising_category | recurring_product_issue | repeated_service_failure | escalation_spike
    kind: str
    key: str
    label: str
    current: int
    previous: int
    change_pct: float | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _change(current: int, previous: int) -> float | None:
    return round(100 * (current - previous) / previous, 1) if previous else None


def _rising(current: int, previous: int, cfg: dict[str, Any], watched: bool = False) -> bool:
    if current < cfg["min_count"]:
        return False
    if watched:
        return current > previous
    return current >= float(cfg["rise_ratio"]) * max(previous, 1)


def _counts(
    db: Session, f: Filters, key: Any, start: datetime, end: datetime, *where: Any
) -> dict[Any, int]:
    stmt = (
        scoped(f, key.label("key"), func.count().label("n"))
        .where(Complaint.created_at >= start, Complaint.created_at < end, *where)
        .group_by(key)
    )
    return {row.key: row.n for row in db.execute(stmt).all()}


def _describe(current: int, previous: int, days: int) -> str:
    change = _change(current, previous)
    if change is None:
        return f"{current} in the last {days} days (none in the {days} days before)."
    return f"{current} in the last {days} days vs {previous} before ({change:+.0f}%)."


def detect_trends(
    db: Session, f: Filters | None = None, now: datetime | None = None
) -> list[Trend]:
    cfg = analytics_config()["trends"]
    now = now or datetime.now(UTC)
    days = int(cfg["window_days"])
    window = timedelta(days=days)
    cur, prev = (now - window, now), (now - 2 * window, now - window)
    f = replace(f or Filters(), date_from=None, date_to=None)  # the windows set the dates
    names = labels(db)
    trends: list[Trend] = []

    category = Complaint.category_code
    now_by_cat = _counts(db, f, category, *cur, category.is_not(None))
    before_by_cat = _counts(db, f, category, *prev, category.is_not(None))
    for code, n in now_by_cat.items():
        before = before_by_cat.get(code, 0)
        if _rising(n, before, cfg, watched=code in cfg["watched_categories"]):
            name = names["category"].get(code, code)
            trends.append(
                Trend(
                    "rising_category",
                    code,
                    f"Rising {name.lower()} complaints",
                    n,
                    before,
                    _change(n, before),
                    _describe(n, before, days),
                )
            )

    pair = func.concat(PRODUCT, "|", Complaint.subcategory_code)
    now_by_pair = _counts(db, f, pair, *cur, Complaint.subcategory_code.is_not(None))
    before_by_pair = _counts(db, f, pair, *prev, Complaint.subcategory_code.is_not(None))
    for key, n in now_by_pair.items():
        product, subcategory = key.split("|", 1)
        if n < cfg["recurring_min_count"] or product == "UNKNOWN":
            continue
        before = before_by_pair.get(key, 0)
        issue = names["subcategory"].get(subcategory, subcategory).lower()
        trends.append(
            Trend(
                "recurring_product_issue",
                key,
                f"Recurring {issue} ({product.replace('_', ' ').lower()})",
                n,
                before,
                _change(n, before),
                _describe(n, before, days),
            )
        )

    department = Complaint.department_code
    now_rep = _counts(db, f, department, *cur, IS_REPEAT, department.is_not(None))
    before_rep = _counts(db, f, department, *prev, IS_REPEAT, department.is_not(None))
    for code, n in now_rep.items():
        before = before_rep.get(code, 0)
        if _rising(n, before, cfg):
            name = names["department"].get(code, code)
            trends.append(
                Trend(
                    "repeated_service_failure",
                    code,
                    f"Repeat complaints rising in {name}",
                    n,
                    before,
                    _change(n, before),
                    _describe(n, before, days),
                )
            )

    everything = literal("all")
    escalated_now = _counts(db, f, everything, *cur, IS_ESCALATED).get("all", 0)
    escalated_before = _counts(db, f, everything, *prev, IS_ESCALATED).get("all", 0)
    if _rising(escalated_now, escalated_before, cfg):
        trends.append(
            Trend(
                "escalation_spike",
                "all",
                "Escalation spike",
                escalated_now,
                escalated_before,
                _change(escalated_now, escalated_before),
                _describe(escalated_now, escalated_before, days),
            )
        )

    return sorted(trends, key=lambda t: (-(t.current - t.previous), -t.current, t.key))
