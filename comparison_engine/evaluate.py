"""Evaluate an unseen complaint pack: import it, run both pipelines, compare, time.

    uv run python -m comparison_engine.evaluate hidden_test_ready/holdout    # GenAI + Python
    uv run python -m comparison_engine.evaluate hidden_test_ready/holdout --python-only
    uv run python -m comparison_engine.evaluate path/to/evaluator_pack --limit 20

A pack is a folder with `complaints.jsonl` (the dataset record format; `expected` labels are
optional) and, optionally, `customers.csv` and `orders.csv`. Complaints are imported through
the normal intake path with `source="evaluation"`, so nothing about the application changes
for hidden data.

The GenAI mode runs Pipeline 1 then Pipeline 2 exactly as the worker does and measures the
wall-clock time of each complaint against the 20-second target. The Python-only mode runs
Pipeline 2 without any GenAI output and writes nothing to the database.

Output: `reports/evaluation_<pack>.csv` (one row per complaint, the SRS comparison columns
plus the expected labels and latency) and `reports/evaluation_<pack>_summary.json`.
"""

import argparse
import asyncio
import csv
import json
import statistics
import sys
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import select

from comparison_engine.labels import expected_labels
from database.models import Complaint, ValidationRun
from database.session import sync_session
from genai_pipeline.pipeline import run_analysis
from genai_pipeline.providers import ProviderUnavailableError, get_provider
from knowledge_base.embeddings import get_embedder
from python_validation.checks import validate
from python_validation.pipeline import build_input, run_validation
from sample_complaints.load_dataset import load
from src.core.config import ROOT_DIR, get_settings
from src.core.logging import configure_logging

FIELDS = ("category", "department", "urgency", "priority", "escalation_level")
TARGET_SECONDS = 20.0


def _pack(folder: Path) -> dict[str, dict[str, Any]]:
    """Dataset ID -> expected labels (empty when the pack has none), in file order."""
    with (folder / "complaints.jsonl").open(encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    return {r["dataset_id"]: r.get("expected") or {} for r in records}


def _complaints(ids: list[str]) -> list[tuple[str, Any]]:
    with sync_session() as db:
        rows = db.execute(
            select(Complaint.external_ref, Complaint.id).where(
                Complaint.source == "evaluation", Complaint.external_ref.in_(ids)
            )
        ).all()
    order = {ref: i for i, ref in enumerate(ids)}
    return sorted(((str(r[0]), r[1]) for r in rows), key=lambda r: order[r[0]])


def _row(
    ref: str,
    dataset_id: str,
    by_field: dict[str, dict[str, Any]],
    expected: dict[str, Any],
    verdict: str,
    explanation: str,
    policy_refs: str,
    seconds: float | None,
) -> dict[str, Any]:
    acceptable = expected.get("acceptable_categories") or [expected.get("category")]
    row: dict[str, Any] = {
        "complaint_id": ref,
        "dataset_id": dataset_id,
        "expected_category": expected.get("category", ""),
        "acceptable_categories": " ".join(c for c in acceptable if c),
        "expected_escalation": expected.get("escalation_required", ""),
    }
    for name in FIELDS:
        row[f"genai_{name}"] = by_field.get(name, {}).get("genai")
        row[f"python_{name}"] = by_field.get(name, {}).get("python")
    row.update(
        policy_references=policy_refs,
        match="match" if not explanation else "mismatch",
        verification_status=verdict,
        explanation=explanation,
        genai_category_correct=row["genai_category"] in acceptable if expected else "",
        python_category_correct=row["python_category"] in acceptable if expected else "",
        latency_seconds=round(seconds, 2) if seconds is not None else "",
    )
    return row


PROVIDER_ATTEMPTS = 3  # a long run survives brief connection drops


def analyse_with_retries(
    db: Any,
    complaint_id: Any,
    provider: Any,
    embedder: Any,
    settings: Any,
    wait: Callable[[float], None] = time.sleep,
) -> None:
    """Run Pipeline 1, retrying a provider outage twice (30 s, then 60 s) before giving up."""
    for attempt in range(1, PROVIDER_ATTEMPTS + 1):
        try:
            run_analysis(db, complaint_id, provider=provider, embedder=embedder, settings=settings)
            return
        except ProviderUnavailableError:
            if attempt == PROVIDER_ATTEMPTS:
                raise
            wait(30 * attempt)


def run_genai(
    pairs: list[tuple[str, Any]], rerun: bool, labels: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    provider, embedder, settings = get_provider(), get_embedder(), get_settings()
    rows, failures = [], 0
    for dataset_id, complaint_id in pairs:
        with sync_session() as db:
            done = db.scalar(
                select(ValidationRun.id).where(
                    ValidationRun.complaint_id == complaint_id,
                    ValidationRun.analysis_run_id.is_not(None),
                )
            )
            seconds = None
            if rerun or done is None:
                started = time.monotonic()
                try:
                    analyse_with_retries(db, complaint_id, provider, embedder, settings)
                except ProviderUnavailableError as exc:
                    print(f"  {dataset_id}: provider unavailable ({exc}); stopping.")
                    failures += 1
                    break
                validation = run_validation(db, complaint_id)
                seconds = time.monotonic() - started
            else:
                latest = db.scalars(
                    select(ValidationRun)
                    .where(ValidationRun.complaint_id == complaint_id)
                    .order_by(ValidationRun.created_at.desc())
                ).first()
                assert latest is not None
                validation = latest
            complaint = db.get(Complaint, complaint_id)
            assert complaint is not None
            by_field = {r["field"]: r for r in validation.comparison}
            diffs = [r for r in validation.comparison if not r["match"]]
            rows.append(
                _row(
                    complaint.complaint_ref,
                    dataset_id,
                    by_field,
                    (labels or {}).get(dataset_id) or expected_labels(dataset_id) or {},
                    validation.verdict,
                    " | ".join(
                        f"{d['field']}: GenAI {d['genai']} vs Python {d['python']} "
                        f"({d['explanation']})"
                        for d in diffs
                    ),
                    " ".join(validation.python_decision.get("policy_refs", [])),
                    seconds,
                )
            )
            if seconds is not None:
                print(
                    f"  {dataset_id} {complaint.complaint_ref} {validation.verdict:>12} "
                    f"{seconds:5.1f}s"
                )
    return rows, failures


def run_python_only(
    pairs: list[tuple[str, Any]], labels: dict[str, dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    rows = []
    with sync_session() as db:
        for dataset_id, complaint_id in pairs:
            complaint = db.get(Complaint, complaint_id)
            assert complaint is not None
            inp, _, _ = build_input(db, complaint)
            inp.analysis = None
            outcome = validate(inp)
            python = outcome.python_expected()
            by_field = {name: {"genai": None, "python": python[name]} for name in FIELDS}
            rows.append(
                _row(
                    complaint.complaint_ref,
                    dataset_id,
                    by_field,
                    (labels or {}).get(dataset_id) or expected_labels(dataset_id) or {},
                    outcome.verdict,
                    "",
                    " ".join(outcome.decision.policy_refs),
                    None,
                )
            )
            rows[-1]["classifier_confidence"] = outcome.classification.confidence
    return rows


def summarise(rows: list[dict[str, Any]], genai: bool, failures: int) -> dict[str, Any]:
    labelled = [r for r in rows if r["expected_category"]]
    n = len(rows)

    def share(values: list[bool]) -> float | None:
        return round(100 * sum(values) / len(values), 1) if values else None

    def escalated(value: Any) -> bool:
        return bool(value) and int(value) >= 1

    summary: dict[str, Any] = {
        "mode": "genai+python" if genai else "python-only",
        "complaints": n,
        "labelled": len(labelled),
        "python_category_accuracy_pct": share([r["python_category_correct"] for r in labelled]),
        "python_escalation_agreement_pct": share(
            [
                escalated(r["python_escalation_level"]) == bool(r["expected_escalation"])
                for r in labelled
                if r["expected_escalation"] != ""
            ]
        ),
        "verdicts": dict(Counter(str(r["verification_status"]) for r in rows)),
    }
    if genai:
        timed = [r["latency_seconds"] for r in rows if r["latency_seconds"] != ""]
        summary.update(
            genai_category_accuracy_pct=share([r["genai_category_correct"] for r in labelled]),
            genai_escalation_agreement_pct=share(
                [
                    escalated(r["genai_escalation_level"]) == bool(r["expected_escalation"])
                    for r in labelled
                    if r["expected_escalation"] != ""
                ]
            ),
            genai_python_agreement_pct={
                name: share([r[f"genai_{name}"] == r[f"python_{name}"] for r in rows])
                for name in FIELDS
            },
            mismatched_complaints=sum(r["match"] == "mismatch" for r in rows),
            provider_failures=failures,
            latency_seconds={
                "timed": len(timed),
                "median": round(statistics.median(timed), 2) if timed else None,
                "p95": round(sorted(timed)[max(0, int(len(timed) * 0.95) - 1)], 2)
                if timed
                else None,
                "max": max(timed) if timed else None,
                "within_20s_pct": share([t <= TARGET_SECONDS for t in timed]),
            },
        )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate an unseen complaint pack")
    parser.add_argument("pack", type=Path)
    parser.add_argument("--python-only", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--rerun", action="store_true", help="Analyse again even if done")
    args = parser.parse_args()
    configure_logging("WARNING", json=False)
    folder: Path = args.pack.resolve()
    genai = not args.python_only
    settings = get_settings()
    if genai and not settings.genai_api_key:
        print(
            f"{settings.genai_api_key_name} is not set in .env "
            "(use --python-only to run Pipeline 2 alone)."
        )
        return 1

    outcomes = asyncio.run(load(folder, source="evaluation"))
    print("Import: " + ", ".join(f"{count} {outcome}" for outcome, count in outcomes.items()))
    labels = _pack(folder)
    ids = list(labels)[: args.limit] if args.limit else list(labels)
    pairs = _complaints(ids)
    if genai:
        rows, failures = run_genai(pairs, args.rerun, labels)
    else:
        rows, failures = run_python_only(pairs, labels), 0
    if not rows:
        print("Nothing evaluated.")
        return 1

    name = folder.name + ("" if genai else "_python_only")
    reports = ROOT_DIR / "reports"
    reports.mkdir(exist_ok=True)
    csv_path = reports / f"evaluation_{name}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = summarise(rows, genai, failures)
    (reports / f"evaluation_{name}_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"Wrote {csv_path.relative_to(ROOT_DIR)}")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
