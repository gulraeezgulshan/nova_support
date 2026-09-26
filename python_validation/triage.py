"""Python-only triage: run Pipeline 2 on complaints that have never been validated.

This is what happens automatically when the GenAI provider is unavailable: the rule matrix
sets the category, department, priority, escalation and SLA deadlines, and every complaint
goes to manual review because no GenAI analysis was checked. Useful to populate the
dashboards before an API key is configured; a later GenAI analysis re-validates each one.

    uv run python -m python_validation.triage --limit 100
"""

import argparse
import sys
from collections import Counter

from sqlalchemy import select

from database.models import Complaint
from database.session import sync_session
from python_validation.pipeline import run_validation
from src.core.logging import configure_logging


def main() -> int:
    parser = argparse.ArgumentParser(description="Python-only validation of unvalidated complaints")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--source", default="dataset")
    args = parser.parse_args()
    configure_logging("WARNING", json=False)
    with sync_session() as db:
        ids = db.scalars(
            select(Complaint.id)
            .where(Complaint.verification.is_(None), Complaint.source == args.source)
            .order_by(Complaint.created_at)
            .limit(args.limit)
        ).all()
    verdicts: Counter[str] = Counter()
    for complaint_id in ids:
        with sync_session() as db:
            verdicts[run_validation(db, complaint_id).verdict] += 1
    print(f"Validated {len(ids)} complaint(s) with Python only: {dict(verdicts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
