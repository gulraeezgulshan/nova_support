import uuid
from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.models.taxonomy import Department


class Role(StrEnum):
    CUSTOMER = "customer"
    AGENT = "agent"
    REVIEWER = "reviewer"
    MANAGER = "manager"
    ADMIN = "admin"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Local user record. Clerk proves identity; this table is the source of truth for roles."""

    __tablename__ = "users"

    clerk_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    full_name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(String(20), default=Role.CUSTOMER)
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    department: Mapped[Department | None] = relationship(lazy="selectin")
