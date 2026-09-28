"""One received e-mail → a new complaint, a message on an existing one, or an answer.

Shared by the scheduled mailbox check (`via="imap"`) and the staff "Process an e-mail"
tool (`via="manual"`). New complaints go through the normal intake (`submit_complaint`).
"""

from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from complaint_processing.attachments import AttachmentError, add_attachment
from complaint_processing.customers import customer_for_email
from complaint_processing.preprocessing import sanitize_text
from complaint_processing.sensitive import redact
from complaint_processing.service import (
    MIN_TITLE_CHARS,
    ComplaintInput,
    ComplaintValidationError,
    DuplicateComplaintError,
    enqueue_automatic,
    submit_complaint,
)
from database import audit
from database.models import Complaint, ComplaintEvent, InboundEmail, Order, OutboundEmail
from email_channel.outbound import compose, queue, reply_subject
from email_channel.parsing import ParsedEmail, clean_subject, complaint_ref_in, order_ref_in
from src.core.storage import Storage

Via = Literal["imap", "manual"]


def new_record(parsed: ParsedEmail, via: Via) -> InboundEmail:
    """A received-mail row, with header values cut to their column sizes."""
    return InboundEmail(
        message_id=parsed.message_id[:300],
        from_address=parsed.from_address[:320],
        from_name=(parsed.from_name or "")[:200] or None,
        subject=parsed.subject[:500],
        outcome="failed",
        via=via,
        attempts=0,
    )


def _title(parsed: ParsedEmail) -> str:
    """The subject, or the body's first line when the subject is missing or too short."""
    subject = clean_subject(parsed.subject)
    if len(subject) >= MIN_TITLE_CHARS:
        return subject[:200]
    first_line = next((line.strip() for line in parsed.body.split("\n") if line.strip()), "")
    return (first_line[:80].rsplit(" ", 1)[0] if len(first_line) > 80 else first_line) or subject


async def _thread_complaint(db: AsyncSession, parsed: ParsedEmail) -> Complaint | None:
    """The complaint this message replies to: [CMP-…] in the subject, or our Message-ID."""
    ref = complaint_ref_in(parsed.subject)
    if ref:
        return await db.scalar(select(Complaint).where(Complaint.complaint_ref == ref))
    ids = [i for i in [parsed.in_reply_to, *parsed.references] if i]
    if not ids:
        return None
    complaint_id = await db.scalar(
        select(OutboundEmail.complaint_id).where(OutboundEmail.message_id.in_(ids)).limit(1)
    )
    return await db.get(Complaint, complaint_id) if complaint_id else None


async def _attach_all(
    db: AsyncSession, complaint: Complaint, parsed: ParsedEmail, storage: Storage
) -> None:
    for item in parsed.attachments:
        try:
            await add_attachment(
                db,
                complaint,
                filename=item.filename,
                data=item.data,
                source="email",
                uploaded_by=None,
                storage=storage,
            )
        except AttachmentError as exc:
            db.add(
                ComplaintEvent(
                    complaint_id=complaint.id,
                    event_type="attachment_skipped",
                    customer_visible=False,
                    message=f"E-mail attachment {item.filename[:120]!r} was not saved: {exc}",
                )
            )


async def process_email(
    db: AsyncSession,
    parsed: ParsedEmail,
    *,
    via: Via,
    own_address: str | None,
    storage: Storage,
) -> InboundEmail:
    record = await db.scalar(
        select(InboundEmail).where(InboundEmail.message_id == parsed.message_id[:300])
    )
    if record is not None and record.outcome != "failed":
        return record  # already handled: never processed twice
    if record is None:
        record = new_record(parsed, via)
        db.add(record)
    record.attempts += 1
    name = parsed.from_name

    if (
        parsed.automated
        or not parsed.from_address
        or (own_address and parsed.from_address == own_address.strip().lower())
    ):
        record.outcome, record.reason = "ignored", "Automatic message or sent by us."
        await db.commit()
        return record

    thread = await _thread_complaint(db, parsed)
    if thread is not None and (thread.customer.email or "").lower() == parsed.from_address:
        text = redact(sanitize_text(parsed.body)).text
        if text:
            db.add(
                ComplaintEvent(
                    complaint_id=thread.id,
                    event_type="customer_message",
                    message=f"Customer message (email): {text}",
                    customer_visible=True,
                )
            )
        await _attach_all(db, thread, parsed, storage)
        record.outcome, record.complaint_id = "appended", thread.id
        await audit.record(
            db, "email.appended", "complaint", thread.id, after={"message_id": parsed.message_id}
        )
        await db.commit()
        return record

    customer = await customer_for_email(db, parsed.from_address[:320], name and name[:200])
    order_ref = order_ref_in(f"{parsed.subject}\n{parsed.body}")
    if order_ref:
        owned = await db.scalar(
            select(Order.id).where(Order.order_ref == order_ref, Order.customer_id == customer.id)
        )
        order_ref = order_ref if owned else None  # someone else's order is simply not linked
    title = _title(parsed)
    references = [*parsed.references, parsed.message_id]
    try:
        complaint = await submit_complaint(
            db,
            customer=customer,
            submitted_by=None,
            source="email",
            enqueue=False,
            commit=False,  # filed together with its attachments and acknowledgement, or not at all
            data=ComplaintInput(
                title=title, description=parsed.body, order_ref=order_ref, channel="email"
            ),
        )
    except ComplaintValidationError as exc:
        reason = " ".join(exc.issues)
        queue(
            db,
            complaint_id=None,
            to=parsed.from_address,
            kind="rejected",
            subject=reply_subject(parsed.subject, None),
            body=compose("rejected", name=name, reason=reason),
            in_reply_to=parsed.message_id,
            references=references,
        )
        record.outcome, record.reason = "rejected", reason
        await db.commit()
        return record
    except DuplicateComplaintError as exc:
        existing = await db.scalar(
            select(Complaint).where(Complaint.complaint_ref == exc.existing_ref)
        )
        queue(
            db,
            complaint_id=existing.id if existing else None,
            to=parsed.from_address,
            kind="duplicate",
            subject=reply_subject(parsed.subject, exc.existing_ref),
            body=compose("duplicate", name=name, ref=exc.existing_ref),
            in_reply_to=parsed.message_id,
            references=references,
        )
        record.outcome, record.reason = "duplicate", str(exc)
        record.complaint_id = existing.id if existing else None
        await db.commit()
        return record

    await _attach_all(db, complaint, parsed, storage)
    queue(
        db,
        complaint_id=complaint.id,
        to=parsed.from_address,
        kind="acknowledgement",
        subject=reply_subject(parsed.subject, complaint.complaint_ref),
        body=compose("acknowledgement", name=name, ref=complaint.complaint_ref),
        in_reply_to=parsed.message_id,
        references=references,
    )
    record.outcome, record.complaint_id = "filed", complaint.id
    await db.commit()
    enqueue_automatic(complaint.id, None)
    return record
