"""Configurable complaint taxonomy: departments, categories, subcategories and SLAs.

These are data, not code, so evaluators can add a category or department at runtime
without a redeploy (SRS 1.8 items 5 and 14).
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Department(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "departments"

    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    subcategories: Mapped[list["Subcategory"]] = relationship(
        back_populates="category", lazy="selectin", order_by="Subcategory.code"
    )


class Subcategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subcategories"
    __table_args__ = (UniqueConstraint("category_id", "code"),)

    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped[Category] = relationship(back_populates="subcategories")


class SlaPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Response and resolution targets per priority (P0-P3)."""

    __tablename__ = "sla_policies"

    priority: Mapped[str] = mapped_column(String(4), unique=True)
    name: Mapped[str] = mapped_column(String(60))
    first_response_minutes: Mapped[int] = mapped_column(Integer)
    resolution_minutes: Mapped[int] = mapped_column(Integer)
    # Flag a complaint as "at risk" once this share of the resolution window has elapsed.
    at_risk_threshold_pct: Mapped[int] = mapped_column(Integer, default=75)
