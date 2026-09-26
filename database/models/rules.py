"""The Complaint Resolution Rule Matrix, stored as data so it can change at runtime.

Seeded from the CSV files in `complaint_rules/` and `escalation_rules/`; editable through the
admin API. The GenAI model never writes these rules (SRS Step 8).
"""

from enum import StrEnum

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RuleType(StrEnum):
    RESOLUTION = "resolution"  # category/subcategory specific handling
    ESCALATION = "escalation"  # applies to any complaint whose facts match


class Rule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rules"

    rule_id: Mapped[str] = mapped_column(String(20), unique=True)  # e.g. DEL-003, ESC-012
    rule_type: Mapped[RuleType] = mapped_column(String(20), index=True)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(40), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(60))
    condition: Mapped[str] = mapped_column(Text, default="")  # safe expression, "" = always
    department: Mapped[str | None] = mapped_column(String(40))
    supporting_departments: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    urgency: Mapped[str | None] = mapped_column(String(20))
    priority: Mapped[str | None] = mapped_column(String(4))
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    required_actions: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)
    prohibited_actions: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)
    policy_refs: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    follow_up_type: Mapped[str | None] = mapped_column(String(40))
    follow_up_hours: Mapped[int | None] = mapped_column(Integer)
    rule_priority: Mapped[int] = mapped_column(Integer, default=50)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
