"""Run-time settings (single row, id 1) and the periodic-job gate."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class AppSettingsRow(Base):
    """Only the settings an administrator changed; everything else follows the defaults."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class JobRun(Base):
    """When each periodic job last ran (see app_settings.jobs.claim)."""

    __tablename__ = "job_runs"

    job: Mapped[str] = mapped_column(String(60), primary_key=True)
    last_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
