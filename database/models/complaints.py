"""Simulated customers and orders, complaints, and the complaint status timeline."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    Sequence,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from src.core.config import get_settings

# Human-readable reference numbers (CMP-000123, CUST-000045) come from database sequences,
# so they are unique even when several workers create records at the same time.
COMPLAINT_REF_SEQ = Sequence("complaint_ref_seq", metadata=Base.metadata)
CUSTOMER_REF_SEQ = Sequence("customer_ref_seq", metadata=Base.metadata)


class CustomerType(StrEnum):
    STANDARD = "STANDARD"
    VOLTCARE_PLUS = "VOLTCARE_PLUS"
    VIP = "VIP"
    BUSINESS = "BUSINESS"


class ComplaintStatus(StrEnum):
    NEW = "new"
    ANALYZED = "analyzed"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    AWAITING_CUSTOMER = "awaiting_customer"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    customer_ref: Mapped[str] = mapped_column(String(20), unique=True)  # CUST-000123
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    customer_type: Mapped[CustomerType] = mapped_column(String(20), default=CustomerType.STANDARD)
    # Set when the customer has a SupportNova login; simulated dataset customers have none.
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), unique=True)

    orders: Mapped[list["Order"]] = relationship(
        back_populates="customer", order_by="Order.order_date.desc()"
    )


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Simulated order history, used to verify references and policy eligibility."""

    __tablename__ = "orders"

    order_ref: Mapped[str] = mapped_column(String(20), unique=True)  # ORD-240001
    transaction_ref: Mapped[str | None] = mapped_column(String(24), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    product_name: Mapped[str] = mapped_column(String(200))
    product_category: Mapped[str] = mapped_column(String(40))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    shipping_method: Mapped[str] = mapped_column(String(20), default="standard")
    order_date: Mapped[date] = mapped_column(Date)
    committed_delivery_date: Mapped[date] = mapped_column(Date)
    delivered_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="delivered")

    customer: Mapped[Customer] = relationship(back_populates="orders")


class Complaint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "complaints"
    __table_args__ = (Index("ix_complaints_customer_hash", "customer_id", "content_hash"),)

    complaint_ref: Mapped[str] = mapped_column(String(20), unique=True)  # CMP-000123
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"))
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)  # sanitised original wording
    normalized_text: Mapped[str] = mapped_column(Text)  # lower-case, normalised, for matching
    content_hash: Mapped[str] = mapped_column(String(64))
    product_service: Mapped[str | None] = mapped_column(String(200))
    channel: Mapped[str] = mapped_column(String(20), default="web_form")
    preferred_contact_channel: Mapped[str | None] = mapped_column(String(20))
    requested_resolution: Mapped[str | None] = mapped_column(Text)
    previous_complaint_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("complaints.id"))
    # Near-duplicate / reworded repeat detection (SRS Steps 52-54).
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("complaints.id"))
    related_complaint_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("complaints.id"))
    similarity: Mapped[float | None] = mapped_column(Float)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(get_settings().embedding_dim))
    source: Mapped[str] = mapped_column(String(20), default="portal")  # portal|dataset|evaluation
    # ID in an imported dataset or evaluation pack (e.g. DS-0042), for scoring against labels.
    external_ref: Mapped[str | None] = mapped_column(String(40), index=True)

    status: Mapped[ComplaintStatus] = mapped_column(
        String(20), default=ComplaintStatus.NEW, index=True
    )
    needs_review: Mapped[bool] = mapped_column(default=False, index=True)
    review_reason: Mapped[str | None] = mapped_column(Text)

    # Deterministic intake results: extracted entities, risk signals, warnings.
    entities: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    signals: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    intake_warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)

    # Current working classification (set from the validated analysis).
    category_code: Mapped[str | None] = mapped_column(String(40), index=True)
    subcategory_code: Mapped[str | None] = mapped_column(String(60))
    department_code: Mapped[str | None] = mapped_column(String(40), index=True)
    urgency: Mapped[str | None] = mapped_column(String(20))
    priority: Mapped[str | None] = mapped_column(String(4), index=True)
    sentiment: Mapped[str | None] = mapped_column(String(20))
    escalation_level: Mapped[int | None] = mapped_column()
    supporting_departments: Mapped[list[str]] = mapped_column(JSONB, default=list)
    verification: Mapped[str | None] = mapped_column(String(20), index=True)  # latest verdict
    # The customer response a reviewer approved or edited; drafts stay in the analysis run.
    approved_response: Mapped[str | None] = mapped_column(Text)

    # SLA tracking (SRS Steps 55-56). Deadlines come from the priority's SLA policy and are
    # measured from submission; `sla_status` is kept current by the periodic SLA scan.
    first_response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)

    customer: Mapped[Customer] = relationship(lazy="joined")
    order: Mapped[Order | None] = relationship(lazy="joined")


class ComplaintEvent(Base):
    """Status timeline shown to customers and staff."""

    __tablename__ = "complaint_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(40))  # submitted, status_changed, analysis_*
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    customer_visible: Mapped[bool] = mapped_column(default=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
