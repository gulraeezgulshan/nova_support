"""Mailbox console: status, received and sent e-mails, and processing an e-mail by hand."""

import re
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from complaint_processing.attachments import MAX_ATTACHMENT_BYTES
from database.models import Complaint, InboundEmail, MailboxState, OutboundEmail, User
from database.session import get_db
from email_channel.inbound import process_email
from email_channel.parsing import parse_email
from security.dependencies import STAFF_ROLES, require_roles
from src.api.schemas import EMAIL_PATTERN, InboundEmailOut, MailboxStatusOut, OutboundEmailOut
from src.core.config import get_settings
from src.core.storage import Storage, get_storage

router = APIRouter(tags=["mailbox"])
staff = require_roles(*STAFF_ROLES)
MAX_EML_BYTES = 10 * 1024 * 1024


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


async def _inbound_out(db: AsyncSession, record: InboundEmail) -> InboundEmailOut:
    ref = (
        await db.scalar(select(Complaint.complaint_ref).where(Complaint.id == record.complaint_id))
        if record.complaint_id
        else None
    )
    return InboundEmailOut(
        id=record.id,
        created_at=record.created_at,
        from_address=record.from_address,
        from_name=record.from_name,
        subject=record.subject,
        outcome=record.outcome,
        reason=record.reason,
        via=record.via,
        complaint_ref=ref,
    )


@router.get("/mailbox", response_model=MailboxStatusOut)
async def mailbox_status(
    _: User = Depends(staff), db: AsyncSession = Depends(get_db)
) -> MailboxStatusOut:
    settings = get_settings()
    state = await db.get(MailboxState, 1)
    return MailboxStatusOut(
        configured=settings.mailbox_configured,
        address=settings.mail_username,
        last_check_at=state.last_check_at if state else None,
        last_error=state.last_error if state else None,
    )


@router.get("/mailbox/inbound", response_model=list[InboundEmailOut])
async def list_inbound_emails(
    limit: int = Query(100, ge=1, le=500),
    _: User = Depends(staff),
    db: AsyncSession = Depends(get_db),
) -> list[InboundEmailOut]:
    rows = await db.execute(
        select(InboundEmail, Complaint.complaint_ref)
        .outerjoin(Complaint, Complaint.id == InboundEmail.complaint_id)
        .order_by(InboundEmail.created_at.desc())
        .limit(limit)
    )
    return [
        InboundEmailOut(
            id=r.id,
            created_at=r.created_at,
            from_address=r.from_address,
            from_name=r.from_name,
            subject=r.subject,
            outcome=r.outcome,
            reason=r.reason,
            via=r.via,
            complaint_ref=ref,
        )
        for r, ref in rows.all()
    ]


@router.get("/mailbox/outbound", response_model=list[OutboundEmailOut])
async def list_outbound_emails(
    limit: int = Query(100, ge=1, le=500),
    _: User = Depends(staff),
    db: AsyncSession = Depends(get_db),
) -> list[OutboundEmailOut]:
    rows = await db.execute(
        select(OutboundEmail, Complaint.complaint_ref)
        .outerjoin(Complaint, Complaint.id == OutboundEmail.complaint_id)
        .order_by(OutboundEmail.created_at.desc())
        .limit(limit)
    )
    return [
        OutboundEmailOut(
            id=e.id,
            created_at=e.created_at,
            to_address=e.to_address,
            kind=e.kind,
            subject=e.subject,
            status=e.status,
            error=e.error,
            sent_at=e.sent_at,
            complaint_ref=ref,
        )
        for e, ref in rows.all()
    ]


@router.post(
    "/mailbox/process", response_model=InboundEmailOut, status_code=status.HTTP_201_CREATED
)
async def process_manual_email(
    eml: UploadFile | None = File(None, description="A saved e-mail (.eml)"),
    from_address: str | None = Form(None),
    from_name: str | None = Form(None),
    subject: str = Form("", max_length=500),
    body: str | None = Form(None, max_length=20_000),
    files: list[UploadFile] = File(default_factory=list),
    _: User = Depends(staff),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> InboundEmailOut:
    """Handle an e-mail exactly as if it had arrived in the mailbox (for demos and forwards)."""
    if eml is not None:
        raw = await eml.read(MAX_EML_BYTES + 1)
        if len(raw) > MAX_EML_BYTES:
            raise _unprocessable("E-mail files must be 10 MB or smaller.")
    else:
        address = (from_address or "").strip()
        if not re.match(EMAIL_PATTERN, address):
            raise _unprocessable("Enter the sender's e-mail address.")
        if not (body or "").strip():
            raise _unprocessable("Paste the e-mail text.")
        message = EmailMessage()
        message["From"] = formataddr(((from_name or "").strip(), address))
        message["Subject"] = subject
        message["Message-ID"] = make_msgid(domain="manual.supportnova")
        message.set_content(body or "")
        for upload in files:
            data = await upload.read(MAX_ATTACHMENT_BYTES + 1)
            maintype, _sep, subtype = (upload.content_type or "application/octet-stream").partition(
                "/"
            )
            message.add_attachment(
                data,
                maintype=maintype,
                subtype=subtype or "octet-stream",
                filename=upload.filename or "attachment",
            )
        raw = bytes(message)
    record = await process_email(
        db,
        parse_email(raw),
        via="manual",
        own_address=get_settings().mail_username,
        storage=storage,
    )
    return await _inbound_out(db, record)
