"""Send the holding message and the approved reply by e-mail, for e-mail complaints only.

Mirrors `support_chat.notify`: at most one holding message and one e-mail per reply text.
"""

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from database.models import Complaint, InboundEmail, OutboundEmail
from email_channel.outbound import SIGNATURE, compose, queue, reply_subject

AUTO_REPLY_VERDICTS = {"verified", "corrected"}


def _origin(complaint: Complaint) -> Select[InboundEmail]:
    """The customer's e-mail that opened the complaint (replies thread under it)."""
    return (
        select(InboundEmail)
        .where(InboundEmail.complaint_id == complaint.id, InboundEmail.outcome == "filed")
        .limit(1)
    )


def _queue(
    db: Session | AsyncSession, complaint: Complaint, origin: InboundEmail, kind: str, body: str
) -> None:
    queue(
        db,
        complaint_id=complaint.id,
        to=origin.from_address,
        kind=kind,
        subject=reply_subject(origin.subject, complaint.complaint_ref),
        body=body,
        in_reply_to=origin.message_id,
        references=[origin.message_id],
    )


def after_validation(
    db: Session, complaint: Complaint, verdict: str, draft: str | None, *, auto_reply: bool = True
) -> None:
    if complaint.channel != "email":
        return
    origin = db.scalar(_origin(complaint))
    if origin is None:
        return
    kinds = set(
        db.scalars(select(OutboundEmail.kind).where(OutboundEmail.complaint_id == complaint.id))
    )
    if "reply" in kinds or complaint.approved_response:
        return  # the customer already has (or will get) the approved reply
    if auto_reply and verdict in AUTO_REPLY_VERDICTS and draft:
        _queue(db, complaint, origin, "reply", draft + SIGNATURE)
    elif (verdict not in AUTO_REPLY_VERDICTS or not auto_reply) and "holding" not in kinds:
        body = compose("holding", name=origin.from_name, ref=complaint.complaint_ref)
        _queue(db, complaint, origin, "holding", body)


async def after_approval(db: AsyncSession, complaint: Complaint) -> None:
    if complaint.channel != "email" or not complaint.approved_response:
        return
    origin = await db.scalar(_origin(complaint))
    if origin is None:
        return
    body = complaint.approved_response + SIGNATURE
    sent = await db.scalar(
        select(OutboundEmail.id).where(
            OutboundEmail.complaint_id == complaint.id,
            OutboundEmail.kind == "reply",
            OutboundEmail.body == body,
        )
    )
    if sent is None:
        _queue(db, complaint, origin, "reply", body)
