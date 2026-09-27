"""E-mail channel: received messages, the outbox, and mailbox status."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class InboundEmail(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Every received message, so nothing is processed twice (keyed by Message-ID)."""

    __tablename__ = "inbound_emails"

    message_id: Mapped[str] = mapped_column(String(300), unique=True)
    from_address: Mapped[str] = mapped_column(String(320))
    from_name: Mapped[str | None] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(500))
    # filed | appended | ignored | rejected | duplicate | failed
    outcome: Mapped[str] = mapped_column(String(20), index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    complaint_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("complaints.id"), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    via: Mapped[str] = mapped_column(String(10))  # imap | manual


class OutboundEmail(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The outbox: queued here in the same transaction as its cause, sent by a periodic flush."""

    __tablename__ = "outbound_emails"

    complaint_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("complaints.id"), index=True)
    to_address: Mapped[str] = mapped_column(String(320))
    # acknowledgement | holding | reply | rejected | duplicate
    kind: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    message_id: Mapped[str] = mapped_column(String(300), unique=True)
    in_reply_to: Mapped[str | None] = mapped_column(String(300))
    references: Mapped[str | None] = mapped_column(Text)
    # queued | sent | failed | not_configured
    status: Mapped[str] = mapped_column(
        String(20), default="queued", server_default="queued", index=True
    )
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MailboxState(Base):
    """Single row (id 1): when the mailbox was last checked and the last problem."""

    __tablename__ = "mailbox_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
