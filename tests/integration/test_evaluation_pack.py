"""Hidden-data readiness: an evaluator pack in the documented format is imported through the
normal intake path and evaluated without any code change."""

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from comparison_engine.evaluate import _complaints, _pack, run_python_only, summarise
from comparison_engine.labels import expected_labels
from database.models import Complaint, Customer
from database.session import sync_session
from sample_complaints.load_dataset import load
from src.core.config import ROOT_DIR

pytestmark = pytest.mark.db


def write_pack(folder: Path) -> None:
    records = [
        {
            "dataset_id": "EV-001",
            "customer_ref": "CUST-800001",
            "title": "Charger sparked",
            "channel": "email",
            "description": "The charger sparked and smelled burnt when I plugged it in.",
            "expected": {
                "category": "SAFETY",
                "acceptable_categories": ["SAFETY"],
                "escalation_required": True,
            },
        },
        {
            "dataset_id": "EV-002",
            "customer_ref": "CUST-800002",
            "title": "Charged twice",
            "description": "My card was charged twice for the same order last week, please fix.",
            "expected": {
                "category": "BILLING",
                "acceptable_categories": ["BILLING"],
                "escalation_required": False,
            },
        },
        {
            "dataset_id": "EV-003",
            "customer_ref": "CUST-800002",
            "title": "Too short",
            "description": "Late.",
        },
    ]
    (folder / "complaints.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")


async def test_evaluator_pack_is_imported_and_evaluated(clean_db: None, tmp_path: Path) -> None:
    write_pack(tmp_path)
    outcomes = await load(tmp_path, source="evaluation")
    assert outcomes == {"accepted": 2, "rejected invalid": 1}
    assert await load(tmp_path, source="evaluation") == {"already loaded": 2, "rejected invalid": 1}

    with sync_session() as db:
        # Customers named only in the complaints file are created on the fly.
        refs = set(db.scalars(select(Customer.customer_ref)))
        assert {"CUST-800001", "CUST-800002"} <= refs
        sources = set(db.scalars(select(Complaint.source)))
        assert sources == {"evaluation"}

    pairs = _complaints(["EV-001", "EV-002", "EV-003"])
    assert [p[0] for p in pairs] == ["EV-001", "EV-002"]
    rows = run_python_only(pairs, _pack(tmp_path))
    safety = next(r for r in rows if r["dataset_id"] == "EV-001")
    assert safety["python_escalation_level"] == 5  # enforced without any GenAI
    summary = summarise(rows, genai=False, failures=0)
    assert summary["complaints"] == 2 and summary["python_escalation_agreement_pct"] == 100.0


def test_holdout_pack_meets_the_srs_minimum() -> None:
    lines = (ROOT_DIR / "hidden_test_ready" / "holdout" / "complaints.jsonl").read_text()
    records = [json.loads(line) for line in lines.splitlines()]
    assert len(records) >= 100
    assert len({r["expected"]["category"] for r in records}) == 12
    labels = expected_labels(records[0]["dataset_id"])  # found by the comparison engine
    assert labels is not None and labels["category"] == records[0]["expected"]["category"]
