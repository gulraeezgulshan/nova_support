"""Contact us enquiries (messages that are not complaints) and newsletter sign-ups."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Sequence, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

ENQUIRY_REF_SEQ = Sequence("enquiry_ref_seq", metadata=Base.metadata)


class EnquiryStatus(StrEnum):
    NEW = "new"
    HANDLED = "handled"


class Enquiry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enquiries"

    ref: Mapped[str] = mapped_column(String(20), unique=True)  # ENQ-000001
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    topic: Mapped[str] = mapped_column(String(30), index=True)
    message: Mapped[str] = mapped_column(Text)  # sanitised and redacted
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"))
    status: Mapped[EnquiryStatus] = mapped_column(
        String(20), default=EnquiryStatus.NEW, server_default=EnquiryStatus.NEW, index=True
    )
    handled_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    complaint_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("complaints.id"))


class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"

    email: Mapped[str] = mapped_column(String(320), primary_key=True)  # lower-cased
    source: Mapped[str] = mapped_column(String(40), default="footer", server_default="footer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
