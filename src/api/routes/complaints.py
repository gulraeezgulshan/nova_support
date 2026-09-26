"""Complaint endpoints. Customers see only their own complaints and never see internal
analysis, signals or review notes; staff see everything."""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from complaint_processing.service import (
    ComplaintInput,
    get_or_create_customer,
    safe_enqueue_analysis,
    submit_complaint,
)
from database import audit
from database.models import (
    AnalysisRun,
    Complaint,
    ComplaintEvent,
    ComplaintStatus,
    Customer,
    Order,
    Role,
    User,
)
from database.session import get_db
from security.dependencies import STAFF_ROLES, get_current_user, require_roles
from src.api.schemas import (
    AnalysisRunOut,
    AnalysisRunSummary,
    ComplaintAnalysisOut,
    ComplaintCreate,
    ComplaintDetail,
    ComplaintEventOut,
    ComplaintPage,
    ComplaintSummary,
    ErrorResponse,
    OrderOut,
)

router = APIRouter(tags=["complaints"])
staff = require_roles(*STAFF_ROLES)


def _is_staff(user: User) -> bool:
    return user.role in STAFF_ROLES


def _summary(complaint: Complaint, staff_view: bool) -> dict[str, Any]:
    data: dict[str, Any] = {
        "complaint_ref": complaint.complaint_ref,
        "title": complaint.title,
        "status": complaint.status,
        "created_at": complaint.created_at,
        "updated_at": complaint.updated_at,
        "customer_ref": complaint.customer.customer_ref,
        "customer_name": complaint.customer.full_name,
        "department_code": complaint.department_code,
        "resolved_at": complaint.resolved_at,
    }
    if staff_view:
        data.update(
            category_code=complaint.category_code,
            priority=complaint.priority,
            urgency=complaint.urgency,
            sentiment=complaint.sentiment,
            escalation_level=complaint.escalation_level,
            needs_review=complaint.needs_review,
            verification=complaint.verification,
            sla_status=complaint.sla_status,
            first_response_due_at=complaint.first_response_due_at,
            resolution_due_at=complaint.resolution_due_at,
            first_responded_at=complaint.first_responded_at,
        )
    return data


async def _latest_updates(
    db: AsyncSession, ids: list[uuid.UUID]
) -> dict[uuid.UUID, ComplaintEvent]:
    """The latest customer-visible timeline entry of each complaint."""
    if not ids:
        return {}
    events = await db.scalars(
        select(ComplaintEvent)
        .where(ComplaintEvent.complaint_id.in_(ids), ComplaintEvent.customer_visible)
        .ext(distinct_on(ComplaintEvent.complaint_id))
        .order_by(
            ComplaintEvent.complaint_id, ComplaintEvent.created_at.desc(), ComplaintEvent.id.desc()
        )
    )
    return {e.complaint_id: e for e in events}


async def _load_for(db: AsyncSession, ref: str, user: User) -> Complaint:
    complaint = await db.scalar(select(Complaint).where(Complaint.complaint_ref == ref.upper()))
    # A customer asking for someone else's complaint gets the same 404 as a missing one.
    if complaint is None or (not _is_staff(user) and complaint.customer.user_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Complaint not found")
    return complaint


@router.post(
    "/complaints",
    response_model=ComplaintDetail,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def create_complaint(
    payload: ComplaintCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComplaintDetail:
    if _is_staff(user):
        if not payload.customer_ref:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "customer_ref is required for staff"
            )
        customer = await db.scalar(
            select(Customer).where(Customer.customer_ref == payload.customer_ref.upper())
        )
        if customer is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    else:
        customer = await get_or_create_customer(db, user)

    data = ComplaintInput(**payload.model_dump(exclude={"customer_ref"}))
    complaint = await submit_complaint(db, customer=customer, data=data, submitted_by=user)
    return await _detail(db, complaint, _is_staff(user))


@router.get("/complaints", response_model=ComplaintPage)
async def list_complaints(
    status_filter: ComplaintStatus | None = Query(None, alias="status"),
    category: str | None = None,
    priority: str | None = None,
    department: str | None = None,
    needs_review: bool | None = None,
    sentiment: str | None = None,
    escalated: bool | None = Query(None, description="Escalation level 1 or higher"),
    sla_status: str | None = None,
    verification: str | None = None,
    date_from: date | None = Query(None, description="Submitted on or after (UTC)"),
    date_to: date | None = Query(None, description="Submitted on or before (UTC)"),
    q: str | None = Query(None, max_length=100, description="Reference, title or customer"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComplaintPage:
    stmt = select(Complaint).join(Customer, Complaint.customer_id == Customer.id)
    if not _is_staff(user):
        stmt = stmt.where(Customer.user_id == user.id)
    if status_filter:
        stmt = stmt.where(Complaint.status == status_filter)
    if category:
        stmt = stmt.where(Complaint.category_code == category)
    if priority:
        stmt = stmt.where(Complaint.priority == priority)
    if department:
        stmt = stmt.where(Complaint.department_code == department)
    if needs_review is not None:
        stmt = stmt.where(Complaint.needs_review == needs_review)
    if sentiment:
        stmt = stmt.where(Complaint.sentiment == sentiment)
    if escalated is not None:
        level = func.coalesce(Complaint.escalation_level, 0)
        stmt = stmt.where(level >= 1 if escalated else level == 0)
    if sla_status:
        stmt = stmt.where(Complaint.sla_status == sla_status)
    if verification:
        stmt = stmt.where(Complaint.verification == verification)
    if date_from:
        stmt = stmt.where(Complaint.created_at >= datetime.combine(date_from, time(), UTC))
    if date_to:
        end = datetime.combine(date_to + timedelta(days=1), time(), UTC)
        stmt = stmt.where(Complaint.created_at < end)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Complaint.complaint_ref.ilike(pattern),
                Complaint.title.ilike(pattern),
                Customer.customer_ref.ilike(pattern),
                Customer.full_name.ilike(pattern),
            )
        )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await db.scalars(
        stmt.order_by(Complaint.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    staff_view = _is_staff(user)
    complaints = list(rows.unique())
    updates = await _latest_updates(db, [c.id for c in complaints])
    items = []
    for c in complaints:
        latest = updates.get(c.id)
        items.append(
            ComplaintSummary(
                **_summary(c, staff_view),
                latest_update=latest.message if latest else None,
                latest_update_at=latest.created_at if latest else None,
            )
        )
    return ComplaintPage(items=items, total=total)


async def _ref(db: AsyncSession, complaint_id: uuid.UUID | None) -> str | None:
    if complaint_id is None:
        return None
    return await db.scalar(select(Complaint.complaint_ref).where(Complaint.id == complaint_id))


async def _detail(db: AsyncSession, complaint: Complaint, staff_view: bool) -> ComplaintDetail:
    events_stmt = (
        select(ComplaintEvent)
        .where(ComplaintEvent.complaint_id == complaint.id)
        .order_by(ComplaintEvent.created_at, ComplaintEvent.id)
    )
    if not staff_view:
        events_stmt = events_stmt.where(ComplaintEvent.customer_visible)
    events = (await db.scalars(events_stmt)).all()
    previous_ref = None
    if complaint.previous_complaint_id:
        previous_ref = await db.scalar(
            select(Complaint.complaint_ref).where(Complaint.id == complaint.previous_complaint_id)
        )
    data: dict[str, Any] = {
        **_summary(complaint, staff_view),
        "description": complaint.description,
        "product_service": complaint.product_service,
        "order": OrderOut.model_validate(complaint.order) if complaint.order else None,
        "channel": complaint.channel,
        "preferred_contact_channel": complaint.preferred_contact_channel,
        "requested_resolution": complaint.requested_resolution,
        "previous_complaint_ref": previous_ref,
        "events": [ComplaintEventOut.model_validate(e) for e in events],
    }
    if staff_view:
        data.update(
            customer_type=str(complaint.customer.customer_type),
            subcategory_code=complaint.subcategory_code,
            signals=complaint.signals,
            entities=complaint.entities,
            intake_warnings=complaint.intake_warnings,
            review_reason=complaint.review_reason,
            verification=complaint.verification,
            supporting_departments=complaint.supporting_departments,
            duplicate_of_ref=await _ref(db, complaint.duplicate_of_id),
            related_complaint_ref=await _ref(db, complaint.related_complaint_id),
            similarity=complaint.similarity,
            approved_response=complaint.approved_response,
        )
    return ComplaintDetail(**data)


@router.get("/complaints/{ref}", response_model=ComplaintDetail)
async def get_complaint(
    ref: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ComplaintDetail:
    return await _detail(db, await _load_for(db, ref, user), _is_staff(user))


@router.get("/complaints/{ref}/analysis", response_model=ComplaintAnalysisOut)
async def get_complaint_analysis(
    ref: str, user: User = Depends(staff), db: AsyncSession = Depends(get_db)
) -> ComplaintAnalysisOut:
    complaint = await _load_for(db, ref, user)
    runs = (
        await db.scalars(
            select(AnalysisRun)
            .where(AnalysisRun.complaint_id == complaint.id)
            .order_by(AnalysisRun.created_at.desc())
        )
    ).all()
    return ComplaintAnalysisOut(
        latest=AnalysisRunOut.model_validate(runs[0]) if runs else None,
        history=[AnalysisRunSummary.model_validate(r) for r in runs],
    )


@router.post("/complaints/{ref}/analyze", status_code=status.HTTP_202_ACCEPTED)
async def reanalyze_complaint(
    ref: str, user: User = Depends(staff), db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    complaint = await _load_for(db, ref, user)
    await audit.record(
        db, "complaint.reanalysis_requested", "complaint", complaint.id, actor_user_id=user.id
    )
    await db.commit()
    safe_enqueue_analysis(complaint.id, user.id)
    return {"status": "queued"}


@router.get("/customers/me/orders", response_model=list[OrderOut])
async def my_orders(
    user: User = Depends(require_roles(Role.CUSTOMER)), db: AsyncSession = Depends(get_db)
) -> list[Order]:
    customer = await db.scalar(
        select(Customer).where(Customer.user_id == user.id).options(selectinload(Customer.orders))
    )
    return list(customer.orders) if customer else []
