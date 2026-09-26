"""GenAI analysis runs, every model call they made, and versioned prompt templates.

Together these provide the evidence the SRS asks for: prompt version, provider, model,
timestamp and policy versions per analysis, plus raw requests/responses, invalid outputs
and retries.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, UUIDPrimaryKeyMixin


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"  # model output stayed invalid after the allowed retries
    FAILED = "failed"  # provider unavailable / unexpected error


class PromptVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "prompt_versions"

    name: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(20))
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    template: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "analysis_runs"

    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[RunStatus] = mapped_column(String(20), default=RunStatus.QUEUED)
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prompt_versions.id"))
    prompt_name: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    provider: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(80))
    schema_version: Mapped[str | None] = mapped_column(String(60))  # contract name + schema hash

    # Knowledge used: chunk code, document ID, version, section, type for each passage.
    retrieved_policies: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # validated GenAI JSON
    validation_errors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    error: Mapped[str | None] = mapped_column(Text)

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LlmCall(Base):
    """One request/response pair with the GenAI provider (including failed attempts)."""

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    attempt: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    request_id: Mapped[str | None] = mapped_column(String(80))
    request: Mapped[dict[str, Any]] = mapped_column(JSONB)  # parameters + rendered prompt
    response_text: Mapped[str | None] = mapped_column(Text)
    stop_reason: Mapped[str | None] = mapped_column(String(40))
    outcome: Mapped[str] = mapped_column(String(20))  # valid | invalid | error
    errors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
