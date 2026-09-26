"""Helpers for writing audit events."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from database.models import AuditEvent


def _event(
    action: str,
    entity_type: str,
    entity_id: str | uuid.UUID,
    actor_user_id: uuid.UUID | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> AuditEvent:
    return AuditEvent(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        actor_user_id=actor_user_id,
        before=before,
        after=after,
    )


async def record(
    db: AsyncSession,
    action: str,
    entity_type: str,
    entity_id: str | uuid.UUID,
    *,
    actor_user_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """Add an audit event to the current transaction (committed with the change it records)."""
    db.add(_event(action, entity_type, entity_id, actor_user_id, before, after))


def record_sync(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str | uuid.UUID,
    *,
    actor_user_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    db.add(_event(action, entity_type, entity_id, actor_user_id, before, after))
