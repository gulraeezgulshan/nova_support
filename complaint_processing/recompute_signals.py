"""Recompute deterministic risk signals for stored complaints after the lexicons in
`config/detectors.yaml` change (e.g. a new escalation keyword added during evaluation).

Usage (repo root): `uv run python -m complaint_processing.recompute_signals`
"""

from sqlalchemy import select

from complaint_processing.detectors import detect_signals
from database.models import Complaint
from database.session import sync_session


def recompute() -> tuple[int, int]:
    changed = total = 0
    with sync_session() as db:
        for complaint in db.scalars(select(Complaint)):
            total += 1
            text = "\n".join(
                filter(
                    None, [complaint.title, complaint.description, complaint.requested_resolution]
                )
            )
            signals = detect_signals(text)
            if signals != complaint.signals:
                complaint.signals = signals
                changed += 1
    return changed, total


if __name__ == "__main__":
    changed, total = recompute()
    print(f"Updated signals on {changed} of {total} complaints.")
