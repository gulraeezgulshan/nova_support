"""Policy-update impact analysis (SRS 1.8 item 4: hidden policy update).

When a new version of a document supersedes an older one, every open complaint whose latest
GenAI analysis relied on the older version is flagged for review: its resolution, escalation
or customer response may need revising.
"""

import uuid
from collections.abc import Mapping
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import audit
from database.models import AnalysisRun, Complaint, ComplaintStatus, Document, DocumentVersion

CLOSED = (ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED)


def flag_affected_complaints(
    db: Session,
    document_id: uuid.UUID,
    superseded_versions: list[str],
    new_version: str,
    actor_user_id: uuid.UUID | None = None,
) -> list[str]:
    """Open a review task for affected open complaints; returns their references."""
    from python_validation.pipeline import open_review_task  # avoid an import cycle

    if not superseded_versions:
        return []
    doc_code = db.scalar(select(Document.doc_code).where(Document.id == document_id))
    latest_per_complaint = (
        select(AnalysisRun.complaint_id, func.max(AnalysisRun.created_at).label("latest"))
        .group_by(AnalysisRun.complaint_id)
        .subquery()
    )
    flagged: list[str] = []
    for old_version in superseded_versions:
        runs = db.scalars(
            select(AnalysisRun)
            .join(
                latest_per_complaint,
                (AnalysisRun.complaint_id == latest_per_complaint.c.complaint_id)
                & (AnalysisRun.created_at == latest_per_complaint.c.latest),
            )
            .where(
                AnalysisRun.retrieved_policies.contains(
                    [{"doc_code": doc_code, "version": old_version}]
                )
            )
        ).all()
        for run in runs:
            complaint = db.get(Complaint, run.complaint_id)
            if complaint is None or complaint.status in CLOSED:
                continue
            reason = (
                f"Policy {doc_code} v{old_version} was superseded by v{new_version} on "
                f"{date.today().isoformat()}; the recommendation may need revision."
            )
            open_review_task(db, complaint, None, [reason])
            complaint.needs_review = True
            complaint.review_reason = reason
            flagged.append(complaint.complaint_ref)
    if flagged:
        audit.record_sync(
            db, "policy.impact_flagged", "document", document_id, actor_user_id=actor_user_id,
            after={"doc_code": doc_code, "new_version": new_version, "complaints": flagged},
        )  # fmt: skip
    return flagged


def superseded_by(changes: Mapping[uuid.UUID, str], versions: list[DocumentVersion]) -> list[str]:
    """Version numbers that an activation plan marks as superseded."""
    by_id = {v.id: v.version for v in versions}
    return [by_id[vid] for vid, status in changes.items() if status == "superseded"]
