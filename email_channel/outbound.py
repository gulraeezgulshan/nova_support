"""Outgoing e-mails: composed here, stored as `queued`, sent by the periodic flush."""

import uuid
from email.utils import make_msgid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import app_settings
from app_settings.texts import render
from database.models import OutboundEmail
from email_channel.parsing import clean_subject


def signature() -> str:
    """The closing added to every complaint e-mail (Settings → Customer texts)."""
    settings = app_settings.runtime()
    text = render(settings.texts.complaint_emails.signature, shop=settings.branding.shop_name)
    return f"\n\n{text}" if text else ""


def compose(
    kind: str, *, name: str | None, ref: str | None = None, reason: str | None = None
) -> str:
    """acknowledgement | holding | rejected | duplicate, with the signature."""
    settings = app_settings.runtime()
    body = render(
        getattr(settings.texts.complaint_emails, kind),
        name=name or "there",
        ref=ref or "",
        reason=reason or "",
        shop=settings.branding.shop_name,
    )
    return body + signature()


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
    order_id: uuid.UUID | None = None,
) -> OutboundEmail:
    email = OutboundEmail(
        complaint_id=complaint_id,
        order_id=order_id,
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
