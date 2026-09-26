"""Ground-truth validation runs, the manual review queue and reviewer decisions.

Reviewer overrides never overwrite the original recommendation: every decision stores the
state before and after (SRS Steps 58-59), in addition to the audit trail.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, UUIDPrimaryKeyMixin


class ReviewStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class ReviewAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    RECLASSIFY = "reclassify"
    REASSIGN = "reassign"
    ESCALATE = "escalate"
    REGENERATE = "regenerate"
    COMMENT = "comment"


class ValidationRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "validation_runs"

    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), index=True
    )
    analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL")
    )
    verdict: Mapped[str] = mapped_column(String(20), index=True)
    score: Mapped[float] = mapped_column(Float)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    python_decision: Mapped[dict[str, Any]] = mapped_column(JSONB)  # expected labels + rules
    comparison: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # GenAI vs Python per field
    final_recommendation: Mapped[dict[str, Any]] = mapped_column(JSONB)
    corrections: Mapped[list[str]] = mapped_column(JSONB, default=list)
    review_reasons: Mapped[list[str]] = mapped_column(JSONB, default=list)
    rules_version: Mapped[str] = mapped_column(String(16))  # fingerprint of the active rules
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ReviewTask(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "review_tasks"

    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), index=True
    )
    validation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("validation_runs.id", ondelete="SET NULL")
    )
    status: Mapped[ReviewStatus] = mapped_column(String(20), default=ReviewStatus.OPEN, index=True)
    reasons: Mapped[list[str]] = mapped_column(JSONB)
    priority: Mapped[str | None] = mapped_column(String(4))
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ReviewerDecision(Base):
    __tablename__ = "reviewer_decisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), index=True
    )
    review_task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("review_tasks.id"))
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[ReviewAction] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(Text)
    before: Mapped[dict[str, Any]] = mapped_column(JSONB)  # recommendation before the decision
    after: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
