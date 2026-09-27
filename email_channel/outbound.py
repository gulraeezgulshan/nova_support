"""Outgoing e-mails: composed here, stored as `queued`, sent by the periodic flush."""

import uuid
from email.utils import make_msgid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from database.models import OutboundEmail
from email_channel.parsing import clean_subject

SIGNATURE = "\n\nKind regards,\nVoltHaven Customer Care"
TEXTS = {
    "acknowledgement": (
        "Hello {name},\n\nThank you for contacting VoltHaven. We have received your complaint "
        "and its reference is {ref}. Our team is looking into it and we will reply in this "
        "e-mail thread. If you have photos or documents, reply to this e-mail with them "
        "attached."
    ),
    "holding": (
        "Hello {name},\n\nA specialist is reviewing your complaint {ref}. We will reply in "
        "this thread as soon as the review is complete."
    ),
    "rejected": (
        "Hello {name},\n\nThank you for your e-mail. We could not open a complaint yet: "
        "{reason}\n\nPlease reply with what happened, when it happened and what you would "
        "like us to do."
    ),
    "duplicate": (
        "Hello {name},\n\nThis matches a complaint you already sent us, reference {ref}. We "
        "are working on it and will reply in that thread."
    ),
}


def compose(
    kind: str, *, name: str | None, ref: str | None = None, reason: str | None = None
) -> str:
    return TEXTS[kind].format(name=name or "there", ref=ref or "", reason=reason or "") + (
        SIGNATURE
    )


def reply_subject(original: str, ref: str | None) -> str:
    base = clean_subject(original) or "Your complaint"
    return f"Re: {base} [{ref}]" if ref else f"Re: {base}"


def queue(
    db: Session | AsyncSession,
    *,
    complaint_id: uuid.UUID | None,
    to: str,
    kind: str,
    subject: str,
    body: str,
    in_reply_to: str | None,
    references: list[str],
) -> OutboundEmail:
    email = OutboundEmail(
        complaint_id=complaint_id,
        to_address=to[:320],
        kind=kind,
        subject=subject[:500],
        body=body,
        message_id=make_msgid(domain="volthaven.supportnova"),
        in_reply_to=in_reply_to[:300] if in_reply_to else None,  # column size
        references=" ".join(references) or None,
        status="queued",
    )
    db.add(email)
    return email
