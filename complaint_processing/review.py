"""Manual review actions and complaint status management (SRS Steps 57-60).

Every reviewer action stores the recommendation before and after it (`ReviewerDecision`)
and an audit event; the original GenAI and Python outputs are never modified.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from complaint_processing import sla
from complaint_processing.facts import build_facts
from complaint_rules.engine import Issue, decide
from complaint_rules.matrix import load_specs_async
from database import audit
from database.models import (
    AnalysisRun,
    Category,
    Complaint,
    ComplaintEvent,
    ComplaintStatus,
    Department,
    ReviewAction,
    ReviewerDecision,
    ReviewStatus,
    ReviewTask,
    RunStatus,
    User,
)

S = ComplaintStatus
TRANSITIONS: dict[ComplaintStatus, set[ComplaintStatus]] = {
    S.NEW: {S.ASSIGNED, S.IN_PROGRESS, S.ESCALATED, S.AWAITING_CUSTOMER, S.CLOSED},
    S.ANALYZED: {S.ASSIGNED, S.IN_PROGRESS, S.ESCALATED, S.AWAITING_CUSTOMER, S.CLOSED},
    S.ASSIGNED: {S.IN_PROGRESS, S.AWAITING_CUSTOMER, S.ESCALATED, S.RESOLVED},
    S.IN_PROGRESS: {S.AWAITING_CUSTOMER, S.ESCALATED, S.RESOLVED},
    S.AWAITING_CUSTOMER: {S.IN_PROGRESS, S.RESOLVED, S.CLOSED},
    S.ESCALATED: {S.IN_PROGRESS, S.RESOLVED},
    S.RESOLVED: {S.CLOSED, S.REOPENED},
    S.CLOSED: {S.REOPENED},
    S.REOPENED: {S.ASSIGNED, S.IN_PROGRESS, S.ESCALATED},
}
STATUS_MESSAGES = {
    ComplaintStatus.ASSIGNED: "Your complaint has been assigned to our team.",
    ComplaintStatus.IN_PROGRESS: "We are working on your complaint.",
    ComplaintStatus.AWAITING_CUSTOMER: "We need some more information from you.",
    ComplaintStatus.ESCALATED: "Your complaint has been escalated to a senior team.",
    ComplaintStatus.RESOLVED: "Your complaint has been resolved.",
    ComplaintStatus.CLOSED: "Your complaint has been closed.",
    ComplaintStatus.REOPENED: "Your complaint has been reopened.",
}


class ReviewError(ValueError):
    pass


@dataclass
class ReviewInput:
    action: ReviewAction
    comment: str | None = None
    response_body: str | None = None
    category: str | None = None
    subcategory: str | None = None
    department: str | None = None
    escalation_level: int | None = None


def snapshot(complaint: Complaint) -> dict[str, Any]:
    return {
        "status": complaint.status,
        "category": complaint.category_code,
        "subcategory": complaint.subcategory_code,
        "department": complaint.department_code,
        "supporting_departments": list(complaint.supporting_departments or []),
        "urgency": complaint.urgency,
        "priority": complaint.priority,
        "escalation_level": complaint.escalation_level,
        "needs_review": complaint.needs_review,
        "approved_response": complaint.approved_response,
    }


def _event(
    complaint: Complaint, message: str, actor: User, visible: bool, to: str | None = None
) -> ComplaintEvent:
    return ComplaintEvent(
        complaint_id=complaint.id,
        event_type="status_changed" if to else "review_action",
        from_status=complaint.status if to else None,
        to_status=to,
        message=message,
        customer_visible=visible,
        actor_user_id=actor.id,
        created_at=datetime.now(UTC),
    )


async def change_status(
    db: AsyncSession,
    complaint: Complaint,
    to_status: ComplaintStatus,
    actor: User,
    note: str | None,
) -> None:
    if to_status == complaint.status:
        return
    if to_status not in TRANSITIONS.get(complaint.status, set()):
        raise ReviewError(f"Cannot move a complaint from {complaint.status} to {to_status}.")
    message = STATUS_MESSAGES.get(to_status, f"Status changed to {to_status}.")
    db.add(
        _event(complaint, f"{message} {note}".strip() if note else message, actor, True, to_status)
    )
    before = complaint.status
    complaint.status = to_status
    now = datetime.now(UTC)
    sla.on_status_change(complaint, to_status, now)
    sla.refresh(complaint, await sla.policy_for_async(db, complaint.priority), now)
    await audit.record(
        db, "complaint.status_changed", "complaint", complaint.id, actor_user_id=actor.id,
        before={"status": before}, after={"status": to_status, "note": note},
    )  # fmt: skip


async def _open_task(db: AsyncSession, complaint: Complaint) -> ReviewTask | None:
    return await db.scalar(
        select(ReviewTask).where(
            ReviewTask.complaint_id == complaint.id, ReviewTask.status == ReviewStatus.OPEN
        )
    )


async def _draft_response(db: AsyncSession, complaint: Complaint) -> str | None:
    run = await db.scalar(
        select(AnalysisRun)
        .where(AnalysisRun.complaint_id == complaint.id, AnalysisRun.status == RunStatus.COMPLETED)
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
    )
    if run is None or not run.output:
        return None
    body: str = run.output["customer_response"]["body"]
    return body


async def _reclassify(
    db: AsyncSession, complaint: Complaint, category: str, subcategory: str
) -> None:
    cat = await db.scalar(select(Category).where(Category.code == category, Category.is_active))
    if cat is None or subcategory not in {s.code for s in cat.subcategories if s.is_active}:
        raise ReviewError(f"{category}/{subcategory} is not an active category/subcategory.")
    history = list(
        (
            await db.scalars(
                select(Complaint).where(
                    Complaint.customer_id == complaint.customer_id,
                    Complaint.id != complaint.id,
                    Complaint.created_at <= complaint.created_at,
                )
            )
        ).all()
    )
    facts = build_facts(complaint, history, complaint.created_at.date())
    decision = decide(await load_specs_async(db), [Issue(category, subcategory)], facts)
    complaint.category_code, complaint.subcategory_code = category, subcategory
    complaint.department_code = decision.department
    complaint.supporting_departments = decision.supporting_departments
    complaint.urgency, complaint.priority = decision.urgency, decision.priority
    # A reviewer may lower nothing that a mandatory escalation rule requires.
    complaint.escalation_level = max(complaint.escalation_level or 0, decision.escalation_level)


async def apply_review(
    db: AsyncSession, complaint: Complaint, reviewer: User, data: ReviewInput
) -> ReviewerDecision:
    from complaint_processing.service import safe_enqueue_analysis

    before = snapshot(complaint)
    task = await _open_task(db, complaint)
    resolve = False
    action = data.action

    if action in (ReviewAction.REJECT, ReviewAction.COMMENT) and not (data.comment or "").strip():
        raise ReviewError("A comment is required.")
    if action == ReviewAction.APPROVE:
        body = data.response_body or await _draft_response(db, complaint)
        if not body:
            raise ReviewError("There is no drafted response to approve; write one or regenerate.")
        complaint.approved_response = body
        sla.on_response_approved(complaint, datetime.now(UTC))
        resolve = True
    elif action == ReviewAction.MODIFY:
        if not (data.response_body or "").strip():
            raise ReviewError("The modified response text is required.")
        complaint.approved_response = data.response_body
        sla.on_response_approved(complaint, datetime.now(UTC))
        resolve = True
    elif action == ReviewAction.REJECT:
        complaint.approved_response = None
        resolve = True
    elif action == ReviewAction.RECLASSIFY:
        if not data.category or not data.subcategory:
            raise ReviewError("Category and subcategory are required.")
        await _reclassify(db, complaint, data.category, data.subcategory)
    elif action == ReviewAction.REASSIGN:
        dept = await db.scalar(
            select(Department).where(Department.code == data.department, Department.is_active)
        )
        if dept is None:
            raise ReviewError(f"Unknown department {data.department}.")
        complaint.department_code = dept.code
    elif action == ReviewAction.ESCALATE:
        level = data.escalation_level
        if level is None or not 1 <= level <= 5:
            raise ReviewError("Escalation level must be between 1 and 5.")
        if level < (complaint.escalation_level or 0):
            raise ReviewError("Escalation cannot be lowered below the current level.")
        complaint.escalation_level = level
        if complaint.status != ComplaintStatus.ESCALATED:
            await change_status(db, complaint, ComplaintStatus.ESCALATED, reviewer, data.comment)
    elif action == ReviewAction.REGENERATE:
        pass  # queued after commit

    if resolve:
        complaint.needs_review = False
        complaint.review_reason = None
        if task is not None:
            task.status = ReviewStatus.RESOLVED
            task.resolved_at = datetime.now(UTC)
            task.resolved_by_id = reviewer.id
        target = (
            ComplaintStatus.IN_PROGRESS
            if action == ReviewAction.REJECT
            else ComplaintStatus.ESCALATED
            if (complaint.escalation_level or 0) >= 1
            else ComplaintStatus.ASSIGNED
        )
        if target in TRANSITIONS.get(complaint.status, set()):
            await change_status(db, complaint, target, reviewer, None)

    sla.refresh(complaint, await sla.policy_for_async(db, complaint.priority), datetime.now(UTC))
    db.add(
        _event(
            complaint,
            f"Reviewer action: {action}" + (f" ({data.comment})" if data.comment else ""),
            reviewer,
            visible=False,
        )
    )
    decision = ReviewerDecision(
        complaint_id=complaint.id,
        review_task_id=task.id if task else None,
        reviewer_id=reviewer.id,
        action=action,
        comment=data.comment,
        before=before,
        after=snapshot(complaint),
    )
    db.add(decision)
    await audit.record(
        db, f"review.{action}", "complaint", complaint.id, actor_user_id=reviewer.id,
        before=before, after=decision.after,
    )  # fmt: skip
    if action in (ReviewAction.APPROVE, ReviewAction.MODIFY):
        from support_chat.notify import after_approval

        await after_approval(db, complaint)
    await db.commit()
    if action == ReviewAction.REGENERATE:
        safe_enqueue_analysis(complaint.id, reviewer.id)
    return decision
