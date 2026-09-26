"""GenAI vs Python comparison report (SRS deliverable 8) and the Python-only baseline.

    uv run python -m comparison_engine.report comparison   # needs analysed complaints
    uv run python -m comparison_engine.report baseline     # Python only, scored on dataset labels

`comparison` uses the latest validation run of every analysed complaint and writes
`reports/genai_python_comparison.csv` with the columns the SRS lists (expected, GenAI and
Python category, department, urgency and escalation, policy references, match, verification
status and the explanation of each disagreement).

`baseline` runs Pipeline 2 without any GenAI output over the dataset complaints and scores
the Python decision against the hand-set labels, without writing anything to the database.
"""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on

from comparison_engine.labels import expected_labels
from database.models import Complaint, ValidationRun
from database.session import sync_session
from python_validation.checks import validate
from python_validation.pipeline import build_input
from src.core.config import ROOT_DIR

REPORTS = ROOT_DIR / "reports"
FIELDS = ("category", "department", "urgency", "priority", "escalation_level")


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def comparison_report(limit: int | None = None) -> tuple[Path, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    agreement: Counter[str] = Counter()
    genai_correct: Counter[str] = Counter()
    python_correct: Counter[str] = Counter()
    labelled = 0
    with sync_session() as db:
        latest = (
            select(ValidationRun)
            .ext(distinct_on(ValidationRun.complaint_id))
            .where(ValidationRun.analysis_run_id.is_not(None))
            .order_by(ValidationRun.complaint_id, ValidationRun.created_at.desc())
        )
        for run in db.scalars(latest.limit(limit) if limit else latest):
            complaint = db.get(Complaint, run.complaint_id)
            assert complaint is not None
            by_field = {row["field"]: row for row in run.comparison}
            expected = expected_labels(complaint.external_ref) or {}
            if expected:
                labelled += 1
            for f in FIELDS:
                agreement[f] += bool(by_field[f]["match"])
                if expected:
                    genai_correct[f] += by_field[f]["genai"] == expected.get(f)
                    python_correct[f] += by_field[f]["python"] == expected.get(f)
            mismatches = [r for r in run.comparison if not r["match"]]
            rows.append({
                "complaint_id": complaint.complaint_ref,
                "dataset_id": complaint.external_ref or "",
                "expected_category": expected.get("category", ""),
                "genai_category": by_field["category"]["genai"],
                "python_category": by_field["category"]["python"],
                "genai_department": by_field["department"]["genai"],
                "python_department": by_field["department"]["python"],
                "genai_urgency": by_field["urgency"]["genai"],
                "python_urgency": by_field["urgency"]["python"],
                "genai_priority": by_field["priority"]["genai"],
                "python_priority": by_field["priority"]["python"],
                "genai_escalation": by_field["escalation_level"]["genai"],
                "python_escalation": by_field["escalation_level"]["python"],
                "policy_references": " ".join(run.python_decision.get("policy_refs", [])),
                "match": "match" if not mismatches else "mismatch",
                "verification_status": run.verdict,
                "score": run.score,
                "explanation": " | ".join(
                    f"{r['field']}: GenAI {r['genai']} vs Python {r['python']} ({r['explanation']})"
                    for r in mismatches
                ),
            })  # fmt: skip
    if not rows:
        raise SystemExit("No analysed complaints yet. Run: uv run python -m genai_pipeline.analyze")
    path = REPORTS / "genai_python_comparison.csv"
    _write(path, rows)
    n = len(rows)
    summary = {
        "complaints": n,
        "labelled": labelled,
        "verified": sum(r["verification_status"] == "verified" for r in rows),
        "corrected": sum(r["verification_status"] == "corrected" for r in rows),
        "needs_review": sum(r["verification_status"] == "needs_review" for r in rows),
        "agreement": {f: round(agreement[f] / n, 3) for f in FIELDS},
        "genai_accuracy": {f: round(genai_correct[f] / labelled, 3) for f in FIELDS}
        if labelled
        else {},
        "python_accuracy": {f: round(python_correct[f] / labelled, 3) for f in FIELDS}
        if labelled
        else {},
    }
    return path, summary


def baseline_report() -> tuple[Path, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    correct: Counter[str] = Counter()
    confidence: Counter[str] = Counter()
    with sync_session() as db:
        complaints = db.scalars(
            select(Complaint).where(Complaint.source == "dataset").order_by(Complaint.complaint_ref)
        ).all()
        for complaint in complaints:
            expected = expected_labels(complaint.external_ref)
            if not expected:
                continue
            inp, _, _ = build_input(db, complaint)
            inp.analysis = None  # Python alone
            outcome = validate(inp)
            python = outcome.python_expected()
            confidence[outcome.classification.confidence] += 1
            row: dict[str, Any] = {"complaint_id": complaint.complaint_ref,
                                   "dataset_id": complaint.external_ref}  # fmt: skip
            for f in FIELDS:
                ok = (
                    python[f] in expected["acceptable_categories"]
                    if f == "category"
                    else python[f] == expected[f]
                )
                correct[f] += ok
                row[f"expected_{f}"] = expected[f]
                row[f"python_{f}"] = python[f]
            row["classifier_confidence"] = outcome.classification.confidence
            rows.append(row)
    path = REPORTS / "python_baseline.csv"
    _write(path, rows)
    n = len(rows)
    return path, {
        "complaints": n,
        "accuracy": {f: round(correct[f] / n, 3) for f in FIELDS},
        "classifier_confidence": dict(confidence),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("mode", choices=["comparison", "baseline"])
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.mode == "comparison":
        path, summary = comparison_report(args.limit)
    else:
        path, summary = baseline_report()
    print(f"Wrote {path.relative_to(ROOT_DIR)}")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
