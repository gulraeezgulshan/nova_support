"""The labelled dataset as evaluation data: records, their text and their rule-matrix facts.

Shared by the dataset test (`tests/unit/test_dataset.py`) and the Patterns page dataset check,
so both judge the patterns the same way.
"""

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from complaint_processing.facts import business_days_between
from complaint_processing.preprocessing import parse_amounts
from complaint_rules.facts import FACTS
from src.core.config import ROOT_DIR

DATASET = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Dataset:
    complaints: list[dict[str, Any]]
    orders: dict[str, dict[str, str]]
    customers: dict[str, dict[str, str]]

    @property
    def accepted(self) -> list[dict[str, Any]]:
        return [c for c in self.complaints if c["expected"]["expected_intake"] == "accepted"]


def load_dataset() -> Dataset:
    with (DATASET / "complaints.jsonl").open(encoding="utf-8") as handle:
        complaints = [json.loads(line) for line in handle]
    with (DATASET / "orders.csv").open(encoding="utf-8") as handle:
        orders = {o["order_ref"]: o for o in csv.DictReader(handle)}
    with (DATASET / "customers.csv").open(encoding="utf-8") as handle:
        customers = {c["customer_ref"]: c for c in csv.DictReader(handle)}
    return Dataset(complaints, orders, customers)


def record_text(record: dict[str, Any]) -> str:
    return "\n".join(
        filter(None, [record["title"], record["description"], record["requested_resolution"]])
    )


def prior_for(record: dict[str, Any], accepted: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The same customer's accepted complaints from at least a day earlier."""
    created = datetime.fromisoformat(record["created_at"])
    return [
        p
        for p in accepted
        if p["customer_ref"] == record["customer_ref"]
        and (created - datetime.fromisoformat(p["created_at"])).total_seconds() >= 86_400
    ]


def facts_for(
    record: dict[str, Any],
    orders: dict[str, dict[str, str]],
    customers: dict[str, dict[str, str]],
    prior: list[dict[str, Any]],
    signals: dict[str, list[str]],
) -> dict[str, Any]:
    today = datetime.fromisoformat(record["created_at"]).date()
    customer = customers[record["customer_ref"]]
    amounts = parse_amounts(record_text(record))
    facts: dict[str, Any] = {
        "customer_type": customer["customer_type"],
        "is_vip": customer["customer_type"] == "VIP",
        "repeat_count": len(prior),
        "unresolved_repeat_count": len(prior),
        "disputed_amount": max(amounts) if amounts else None,
        "has_order": False,
    }
    order = orders.get(record["order_ref"] or "")
    if order:

        def as_date(value: str) -> date | None:
            return date.fromisoformat(value) if value else None

        delivered = as_date(order["delivered_date"])
        committed = as_date(order["committed_delivery_date"])
        assert committed is not None
        facts.update(
            has_order=True,
            order_status=order["status"],
            order_amount=float(order["amount"]),
            shipping_method=order["shipping_method"],
            days_since_order=(today - date.fromisoformat(order["order_date"])).days,
            days_since_delivery=(today - delivered).days if delivered else None,
            days_late=business_days_between(committed, delivered or today),
        )
    for name, spec in FACTS.items():
        if spec.type == "bool" and name not in facts:
            facts[name] = bool(signals.get(name))
    return facts


def yaml_taxonomy() -> dict[str, list[str]]:
    """Every category and subcategory of `config/taxonomy.yaml` (the seeded taxonomy)."""
    with (ROOT_DIR / "config" / "taxonomy.yaml").open(encoding="utf-8") as handle:
        categories = yaml.safe_load(handle)["categories"]
    return {c["code"]: [s["code"] for s in c["subcategories"]] for c in categories}
