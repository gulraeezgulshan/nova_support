"""Contact us (public), the staff enquiries inbox, and newsletter sign-ups."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Complaint, Enquiry, EnquiryStatus, User
from database.session import get_db
from security.dependencies import STAFF_ROLES, get_optional_user, require_roles
from src.api.schemas import (
    ContactIn,
    ContactOut,
    ContactTopic,
    EnquiryOut,
    EnquiryUpdate,
    NewsletterIn,
)
from support_contact.service import ContactError, convert, set_status, submit_contact, subscribe

router = APIRouter(tags=["contact"])
staff = require_roles(*STAFF_ROLES)


def _raise(exc: ContactError) -> HTTPException:
    return HTTPException(exc.status, exc.message)


async def _out(db: AsyncSession, enquiry: Enquiry) -> EnquiryOut:
    complaint_ref = (
        await db.scalar(select(Complaint.complaint_ref).where(Complaint.id == enquiry.complaint_id))
        if enquiry.complaint_id
        else None
    )
    return EnquiryOut(
        ref=enquiry.ref,
        name=enquiry.name,
        email=enquiry.email,
        topic=enquiry.topic,
        message=enquiry.message,
        status=enquiry.status,
        created_at=enquiry.created_at,
        handled_at=enquiry.handled_at,
        complaint_ref=complaint_ref,
        can_convert=enquiry.customer_id is not None and enquiry.complaint_id is None,
    )


async def _enquiry(db: AsyncSession, ref: str) -> Enquiry:
    enquiry = await db.scalar(select(Enquiry).where(Enquiry.ref == ref))
    if enquiry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Enquiry not found")
    return enquiry


@router.post("/contact", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
async def contact(
    payload: ContactIn,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> ContactOut:
    """Order problems (sign-in required) become complaints; other topics become enquiries."""
    if payload.website:  # honeypot: people never fill the hidden field, bots do
        return ContactOut(kind="ignored", reference=None)
    try:
        kind, ref = await submit_contact(
            db,
            user,
            name=payload.name,
            email=payload.email,
            topic=payload.topic,
            message=payload.message,
            order_ref=payload.order_ref or None,
        )
    except ContactError as exc:
        raise _raise(exc) from exc
    return ContactOut(kind=kind, reference=ref)


@router.get("/enquiries", response_model=list[EnquiryOut])
async def list_enquiries(
    status_filter: EnquiryStatus | None = Query(None, alias="status"),
    topic: ContactTopic | None = Query(None),
    _: User = Depends(staff),
    db: AsyncSession = Depends(get_db),
) -> list[EnquiryOut]:
    stmt = select(Enquiry).order_by(Enquiry.created_at.desc(), Enquiry.ref.desc()).limit(500)
    if status_filter:
        stmt = stmt.where(Enquiry.status == status_filter)
    if topic:
        stmt = stmt.where(Enquiry.topic == topic)
    return [await _out(db, e) for e in (await db.scalars(stmt)).all()]


@router.patch("/enquiries/{ref}", response_model=EnquiryOut)
async def update_enquiry(
    ref: str,
    payload: EnquiryUpdate,
    user: User = Depends(staff),
    db: AsyncSession = Depends(get_db),
) -> EnquiryOut:
    enquiry = await _enquiry(db, ref)
    await set_status(db, enquiry, EnquiryStatus(payload.status), user)
    return await _out(db, enquiry)


@router.post("/enquiries/{ref}/convert", response_model=EnquiryOut)
async def convert_enquiry(
    ref: str, user: User = Depends(staff), db: AsyncSession = Depends(get_db)
) -> EnquiryOut:
    """Create a complaint from an enquiry sent by a signed-in customer (once)."""
    enquiry = await _enquiry(db, ref)
    try:
        await convert(db, enquiry, user)
    except ContactError as exc:
        raise _raise(exc) from exc
    return await _out(db, enquiry)


@router.post("/newsletter", status_code=status.HTTP_204_NO_CONTENT)
async def newsletter(payload: NewsletterIn, db: AsyncSession = Depends(get_db)) -> Response:
    """Demo newsletter sign-up: stored once, nothing is ever sent."""
    await subscribe(db, payload.email, payload.source)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
