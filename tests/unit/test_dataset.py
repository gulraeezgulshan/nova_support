"""The labelled complaint dataset meets the SRS minimums, and its hand-set labels agree with
the rule matrix. A disagreement means a rule, a lexicon or a label changed incompatibly."""

import csv
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from complaint_processing.detectors import detect_signals
from complaint_processing.facts import business_days_between
from complaint_processing.preprocessing import parse_amounts
from complaint_rules.engine import Issue, RuleSpec, decide
from complaint_rules.facts import FACTS
from complaint_rules.matrix import read_default_matrix

DATASET = Path(__file__).resolve().parents[2] / "sample_complaints"


@pytest.fixture(scope="module")
def complaints() -> list[dict[str, Any]]:
    with (DATASET / "complaints.jsonl").open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def test_dataset_meets_srs_minimums(complaints: list[dict[str, Any]]) -> None:
    unique = {c["description"] for c in complaints}
    tags = Counter(t for c in complaints for t in c["tags"])
    expected = [c["expected"] for c in complaints]
    assert len(unique) >= 500
    assert len({e["category"] for e in expected}) >= 10
    assert len({e["subcategory"] for e in expected}) >= 20
    assert len({e["department"] for e in expected}) >= 8
    assert tags["ambiguous"] + tags["multi_issue"] >= 25
    assert tags["contradictory"] >= 20
    assert tags["prompt_injection"] >= 20
    assert tags["repeat_complaint"] + tags["near_duplicate"] + tags["exact_duplicate"] >= 25
    for tag in ("calm_critical", "angry_low_priority", "vip_minor", "low_value_privacy",
                "legal_threat", "incomplete", "three_issues"):  # fmt: skip
        assert tags[tag] > 0, tag


def facts_for(
    record: dict[str, Any],
    orders: dict[str, dict[str, str]],
    customers: dict[str, dict[str, str]],
    prior: list[dict[str, Any]],
) -> dict[str, Any]:
    today = datetime.fromisoformat(record["created_at"]).date()
    text = "\n".join(filter(None, [record["title"], record["description"],
                                   record["requested_resolution"]]))  # fmt: skip
    signals = detect_signals(text)
    customer = customers[record["customer_ref"]]
    amounts = parse_amounts(text)
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


def test_labels_agree_with_the_rule_matrix(complaints: list[dict[str, Any]]) -> None:
    rules = [RuleSpec.from_record(r) for r in read_default_matrix()]
    with (DATASET / "orders.csv").open(encoding="utf-8") as handle:
        orders = {o["order_ref"]: o for o in csv.DictReader(handle)}
    with (DATASET / "customers.csv").open(encoding="utf-8") as handle:
        customers = {c["customer_ref"]: c for c in csv.DictReader(handle)}
    accepted = [c for c in complaints if c["expected"]["expected_intake"] == "accepted"]

    mismatches = []
    for record in accepted:
        created = datetime.fromisoformat(record["created_at"])
        prior = [
            p for p in accepted
            if p["customer_ref"] == record["customer_ref"]
            and (created - datetime.fromisoformat(p["created_at"])).total_seconds() >= 86_400
        ]  # fmt: skip
        expected = record["expected"]
        issues = [Issue(expected["category"], expected["subcategory"])] + [
            Issue(*s.split("/")) for s in expected["secondary_issues"]
        ]
        decision = decide(rules, issues, facts_for(record, orders, customers, prior))
        got = (decision.department, decision.priority, decision.urgency, decision.escalation_level)
        want = (expected["department"], expected["priority"], expected["urgency"],
                expected["escalation_level"])  # fmt: skip
        if got != want:
            mismatches.append((record["dataset_id"], record["scenario"], want, got))
    assert mismatches == [], mismatches[:10]
