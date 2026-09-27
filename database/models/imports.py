"""Bulk complaint uploads: one row per uploaded file, with its checked rows."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ImportBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_batches"

    filename: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    # previewed | running | done | failed
    status: Mapped[str] = mapped_column(String(20), default="previewed")
    total: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    # [{"values": {...}, "status": ready|warning|error, "messages": [...],
    #   "result": created|failed, "reference": "CMP-…", "reason": "…"}]
    rows: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
