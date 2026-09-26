"""SLA tracking and risk detection (SRS Steps 55-56).

Response and resolution targets come from the `sla_policies` table (one row per priority,
editable at runtime). The clock starts when the complaint is submitted; deadlines are set
once the complaint has a priority and move if the priority changes.

    pending    no priority yet (waiting for analysis)
    on_track   open, inside the targets
    at_risk    open, past the policy's at-risk share of a window (e.g. 75% of the resolution time)
    breached   open, past a deadline (first response or resolution)
    met        resolved within the resolution target
    missed     resolved after the resolution target

The periodic scan (`scan`, run by Celery Beat) re-evaluates open complaints and records a
staff-only timeline event and an audit event when one becomes at risk or breached.

    uv run python -m complaint_processing.sla    # run one scan now
"""

import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from database import audit
from database.models import Complaint, ComplaintEvent, SlaPolicy
from src.core.domain import analytics_config
from src.core.logging import get_logger

log = get_logger(__name__)


class SlaState(StrEnum):
    PENDING = "pending"
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    MET = "met"
    MISSED = "missed"


OPEN_STATES = {SlaState.PENDING, SlaState.ON_TRACK, SlaState.AT_RISK, SlaState.BREACHED}
ALERT_STATES = {SlaState.AT_RISK, SlaState.BREACHED}


def sla_config() -> dict[str, Any]:
    data: dict[str, Any] = analytics_config()["sla"]
    return data


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def schedule(complaint: Complaint, policy: SlaPolicy | None) -> None:
    """Set the deadlines from the priority's policy (measured from submission)."""
    if policy is None:
        complaint.first_response_due_at = complaint.resolution_due_at = None
        return
    start = _aware(complaint.created_at)
    complaint.first_response_due_at = start + timedelta(minutes=policy.first_response_minutes)
    complaint.resolution_due_at = start + timedelta(minutes=policy.resolution_minutes)


def evaluate(complaint: Complaint, policy: SlaPolicy | None, now: datetime) -> SlaState:
    if policy is None or complaint.resolution_due_at is None:
        return SlaState.PENDING
    resolution_due = _aware(complaint.resolution_due_at)
    if complaint.resolved_at is not None:
        return SlaState.MET if _aware(complaint.resolved_at) <= resolution_due else SlaState.MISSED
    start = _aware(complaint.created_at)
    response_due = _aware(complaint.first_response_due_at or resolution_due)
    responded = complaint.first_responded_at is not None
    if now > resolution_due or (not responded and now > response_due):
        return SlaState.BREACHED
    share = policy.at_risk_threshold_pct / 100
    risky_resolution = now >= start + (resolution_due - start) * share
    risky_response = not responded and now >= start + (response_due - start) * share
    return SlaState.AT_RISK if risky_resolution or risky_response else SlaState.ON_TRACK


def refresh(complaint: Complaint, policy: SlaPolicy | None, now: datetime) -> SlaState | None:
    """Reschedule and re-evaluate; returns the new state if it changed."""
    schedule(complaint, policy)
    state = evaluate(complaint, policy, now)
    if state == complaint.sla_status:
        return None
    complaint.sla_status = state
    return state


def on_status_change(complaint: Complaint, to_status: str, at: datetime) -> None:
    """Record the first response and the resolution time as the status changes."""
    cfg = sla_config()
    if complaint.first_responded_at is None and to_status in cfg["first_response_statuses"]:
        complaint.first_responded_at = at
    if to_status in cfg["resolved_statuses"]:
        complaint.resolved_at = complaint.resolved_at or at
    elif to_status == "reopened":
        complaint.resolved_at = None


def on_response_approved(complaint: Complaint, at: datetime) -> None:
    if complaint.first_responded_at is None:
        complaint.first_responded_at = at


def policy_for(db: Session, priority: str | None) -> SlaPolicy | None:
    if priority is None:
        return None
    return db.scalar(select(SlaPolicy).where(SlaPolicy.priority == priority))


async def policy_for_async(db: AsyncSession, priority: str | None) -> SlaPolicy | None:
    if priority is None:
        return None
    return await db.scalar(select(SlaPolicy).where(SlaPolicy.priority == priority))


def _alert(db: Session, complaint: Complaint, state: SlaState, now: datetime) -> None:
    due = complaint.resolution_due_at
    when = f" (resolution due {due:%Y-%m-%d %H:%M} UTC)" if due else ""
    message = f"SLA breached{when}." if state == SlaState.BREACHED else f"SLA at risk{when}."
    db.add(
        ComplaintEvent(
            complaint_id=complaint.id,
            event_type=f"sla_{state}",
            message=message,
            customer_visible=False,
            created_at=now,
        )
    )
    audit.record_sync(
        db,
        f"sla.{state}",
        "complaint",
        complaint.id,
        after={"priority": complaint.priority, "resolution_due_at": str(due)},
    )


@dataclass
class ScanResult:
    scanned: int = 0
    changed: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    newly_at_risk: list[str] = field(default_factory=list)
    newly_breached: list[str] = field(default_factory=list)


def scan(db: Session, now: datetime | None = None) -> ScanResult:
    """Re-evaluate every complaint whose SLA is still running; alert on new risks."""
    now = now or datetime.now(UTC)
    policies = {p.priority: p for p in db.scalars(select(SlaPolicy))}
    result = ScanResult()
    complaints = db.scalars(
        select(Complaint).where(Complaint.sla_status.in_([s.value for s in OPEN_STATES]))
    ).unique()
    for complaint in complaints:
        result.scanned += 1
        state = refresh(complaint, policies.get(complaint.priority or ""), now)
        current = SlaState(complaint.sla_status)
        result.counts[current.value] = result.counts.get(current.value, 0) + 1
        if state is None:
            continue
        result.changed += 1
        if state in ALERT_STATES:
            _alert(db, complaint, state, now)
            target = result.newly_breached if state == SlaState.BREACHED else result.newly_at_risk
            target.append(complaint.complaint_ref)
    db.commit()
    log.info(
        "sla.scan",
        scanned=result.scanned,
        changed=result.changed,
        at_risk=len(result.newly_at_risk),
        breached=len(result.newly_breached),
    )
    return result


def main() -> int:
    from database.session import sync_session

    with sync_session() as db:
        result = scan(db)
    print(f"Scanned {result.scanned} open complaint(s); {result.changed} changed.")
    print(f"  now: {result.counts}")
    print(f"  newly at risk: {len(result.newly_at_risk)}")
    print(f"  newly breached: {len(result.newly_breached)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
