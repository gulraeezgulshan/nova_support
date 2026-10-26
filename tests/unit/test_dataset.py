"""The labelled complaint dataset meets the SRS minimums, and its hand-set labels agree with
the rule matrix. A disagreement means a rule, a lexicon or a label changed incompatibly."""

from collections import Counter
from typing import Any

import pytest

from complaint_processing.detectors import detect_signals
from complaint_rules.engine import Issue, RuleSpec, decide
from complaint_rules.matrix import read_default_matrix
from sample_complaints.evaluate import facts_for, load_dataset, prior_for, record_text


@pytest.fixture(scope="module")
def complaints() -> list[dict[str, Any]]:
    return load_dataset().complaints


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


def test_labels_agree_with_the_rule_matrix() -> None:
    rules = [RuleSpec.from_record(r) for r in read_default_matrix()]
    data = load_dataset()
    accepted = data.accepted

    mismatches = []
    for record in accepted:
        expected = record["expected"]
        issues = [Issue(expected["category"], expected["subcategory"])] + [
            Issue(*s.split("/")) for s in expected["secondary_issues"]
        ]
        signals = detect_signals(record_text(record))
        facts = facts_for(record, data.orders, data.customers, prior_for(record, accepted), signals)
        decision = decide(rules, issues, facts)
        got = (decision.department, decision.priority, decision.urgency, decision.escalation_level)
        want = (expected["department"], expected["priority"], expected["urgency"],
                expected["escalation_level"])  # fmt: skip
        if got != want:
            mismatches.append((record["dataset_id"], record["scenario"], want, got))
    assert mismatches == [], mismatches[:10]
