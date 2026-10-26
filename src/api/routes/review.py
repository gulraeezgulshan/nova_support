"""Validation results, the manual review queue, reviewer actions and status changes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from complaint_processing.review import ReviewError, ReviewInput, apply_review, change_status
from database.models import (
    Complaint,
    ReviewerDecision,
    ReviewStatus,
    ReviewTask,
    User,
    ValidationRun,
)
from database.session import get_db
from python_validation.pipeline import run_validation
from security.dependencies import require_access
from src.api.routes.complaints import _detail, _load_for, _summary
from src.api.schemas import (
    ComplaintDetail,
    ComplaintSummary,
    ErrorResponse,
    ReviewActionIn,
    ReviewerDecisionOut,
    ReviewTaskOut,
    StatusChangeIn,
    ValidationRunOut,
)

router = APIRouter(tags=["review"])
complaints_view = require_access("complaints", "view")
complaints_edit = require_access("complaints", "edit")
review_view = require_access("review", "view")
review_edit = require_access("review", "edit")


@router.get("/complaints/{ref}/validation", response_model=ValidationRunOut | None)
async def get_validation(
    ref: str, user: User = Depends(complaints_view), db: AsyncSession = Depends(get_db)
) -> ValidationRun | None:
    complaint = await _load_for(db, ref, user)
    return await db.scalar(
        select(ValidationRun)
        .where(ValidationRun.complaint_id == complaint.id)
        .order_by(ValidationRun.created_at.desc())
        .limit(1)
    )


@router.post("/complaints/{ref}/validate", response_model=ValidationRunOut)
async def revalidate(
    ref: str, user: User = Depends(complaints_edit), db: AsyncSession = Depends(get_db)
) -> ValidationRun:
    """Re-run Pipeline 2 now, e.g. after a rule or policy change."""
    complaint = await _load_for(db, ref, user)
    complaint_id = complaint.id
    validation_id = await db.run_sync(lambda s: run_validation(s, complaint_id, user.id).id)
    await db.commit()
    db.expire_all()
    result = await db.get(ValidationRun, validation_id)
    assert result is not None
    return result


@router.get("/review-queue", response_model=list[ReviewTaskOut])
async def review_queue(
    status_filter: ReviewStatus = Query(ReviewStatus.OPEN, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(review_view),
    db: AsyncSession = Depends(get_db),
) -> list[ReviewTaskOut]:
    rows = (
        await db.execute(
            select(ReviewTask, Complaint)
            .join(Complaint, ReviewTask.complaint_id == Complaint.id)
            .where(ReviewTask.status == status_filter)
            .order_by(Complaint.priority.asc().nulls_last(), ReviewTask.created_at)
            .limit(limit)
        )
    ).all()
    return [
        ReviewTaskOut(
            id=task.id,
            status=task.status,
            reasons=task.reasons,
            priority=task.priority,
            created_at=task.created_at,
            resolved_at=task.resolved_at,
            complaint=ComplaintSummary(**_summary(complaint, True)),
        )
        for task, complaint in rows
    ]


@router.post(
    "/complaints/{ref}/review",
    response_model=ReviewerDecisionOut,
    responses={422: {"model": ErrorResponse}},
)
async def review_complaint(
    ref: str,
    payload: ReviewActionIn,
    user: User = Depends(review_edit),
    db: AsyncSession = Depends(get_db),
) -> ReviewerDecision:
    complaint = await _load_for(db, ref, user)
    try:
        return await apply_review(db, complaint, user, ReviewInput(**payload.model_dump()))
    except ReviewError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.get("/complaints/{ref}/decisions", response_model=list[ReviewerDecisionOut])
async def list_decisions(
    ref: str, user: User = Depends(complaints_view), db: AsyncSession = Depends(get_db)
) -> list[ReviewerDecision]:
    complaint = await _load_for(db, ref, user)
    return list(
        (
            await db.scalars(
                select(ReviewerDecision)
                .where(ReviewerDecision.complaint_id == complaint.id)
                .order_by(ReviewerDecision.created_at.desc())
            )
        ).all()
    )


@router.patch(
    "/complaints/{ref}/status",
    response_model=ComplaintDetail,
    responses={422: {"model": ErrorResponse}},
)
async def update_status(
    ref: str,
    payload: StatusChangeIn,
    user: User = Depends(complaints_edit),
    db: AsyncSession = Depends(get_db),
) -> ComplaintDetail:
    complaint = await _load_for(db, ref, user)
    try:
        await change_status(db, complaint, payload.status, user, payload.note)
    except ReviewError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    await db.commit()
    await db.refresh(complaint)  # updated_at is set by the database
    return await _detail(db, complaint, True)
