"""Support chat: conversations with a customer and their messages."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ChatState(StrEnum):
    GATHERING = "gathering"
    CONFIRMING = "confirming"
    SUBMITTING = "submitting"  # claimed by one confirm request; blocks a second one
    SUBMITTED = "submitted"
    CLOSED = "closed"  # abandoned by the customer (Start over)


class ChatConversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_conversations"

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"))
    complaint_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("complaints.id"), unique=True)
    state: Mapped[ChatState] = mapped_column(String(20), default=ChatState.GATHERING)
    # Latest AI draft: title and requested resolution (shown to the customer to confirm).
    draft: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    customer_messages: Mapped[int] = mapped_column(Integer, default=0)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))  # customer | assistant
    # text | order_options | summary | reference | reply | holding | acknowledgement
    kind: Mapped[str] = mapped_column(String(30), default="text")
    content: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
