"""Load, cache and save run-time settings. Readers call `runtime()`."""

import time
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app_settings.defaults import defaults
from app_settings.model import RuntimeSettings
from database import audit
from database.models import AppSettingsRow, User
from database.session import sync_session
from src.core.logging import get_logger

log = get_logger(__name__)

CACHE_SECONDS = 15.0
_cache: tuple[float, RuntimeSettings] | None = None
_override: RuntimeSettings | None = None


class StaleSettingsError(Exception):
    """Someone saved the settings after this admin loaded them."""


def load(data: dict[str, Any] | None) -> RuntimeSettings:
    """Defaults with the stored changes on top; unknown keys ignored.

    Each group is checked on its own: a group with an invalid stored value falls back to
    that group's defaults, and the other groups keep their stored values.
    """
    base = defaults().model_dump()
    stored = data or {}
    merged: dict[str, Any] = {}
    for group, fields in base.items():
        candidate = {
            **fields,
            **{k: v for k, v in (stored.get(group) or {}).items() if k in fields},
        }
        model = RuntimeSettings.model_fields[group].annotation
        try:
            merged[group] = model.model_validate(candidate).model_dump()  # type: ignore[union-attr]
        except ValidationError as exc:
            log.warning("settings.invalid_group", group=group, error=str(exc)[:500])
            merged[group] = fields
    return RuntimeSettings.model_validate(merged)


def override(settings: RuntimeSettings | None) -> None:
    """Tests: use these settings instead of the database (None to stop)."""
    global _override
    _override = settings


def reset_cache() -> None:
    global _cache
    _cache = None


def runtime(fresh: bool = False) -> RuntimeSettings:
    """Current settings, re-read from the database at most every 15 seconds.

    `fresh=True` re-reads now (e.g. before chunking a document, so a value saved a moment
    ago is used) and refreshes the cache.
    """
    global _cache
    if _override is not None:
        return _override
    now = time.monotonic()
    if not fresh and _cache is not None and now - _cache[0] < CACHE_SECONDS:
        return _cache[1]
    try:
        with sync_session() as db:
            row = db.get(AppSettingsRow, 1)
            value = load(row.data if row else None)
    except Exception:  # the system keeps today's behaviour if settings cannot be read
        log.exception("settings.unreadable")
        value = defaults()
    _cache = (now, value)
    return value


def _changes(new: RuntimeSettings) -> dict[str, dict[str, Any]]:
    base, data = defaults().model_dump(), new.model_dump()
    changed = {
        group: {k: v for k, v in fields.items() if base[group].get(k) != v}
        for group, fields in data.items()
    }
    return {group: fields for group, fields in changed.items() if fields}


async def current_row(db: AsyncSession) -> AppSettingsRow | None:
    return await db.get(AppSettingsRow, 1, with_for_update=True)


async def save(
    db: AsyncSession,
    new: RuntimeSettings,
    *,
    actor: User,
    expected_version: int | None,
    action: str = "settings.updated",
    audit_group: str | None = None,
) -> AppSettingsRow:
    """Store the changes from the defaults; `expected_version=None` skips the stale check.

    With `audit_group`, the audit entry holds only that group (e.g. the access matrix).
    """
    row = await current_row(db)
    version = row.version if row else 0
    if expected_version is not None and expected_version != version:
        raise StaleSettingsError
    before = load(row.data if row else None).model_dump()
    if row is None:
        row = AppSettingsRow(id=1, data={}, version=0)
        db.add(row)
    row.data = _changes(new)
    row.version = version + 1
    row.updated_at = datetime.now(UTC)
    row.updated_by_id = actor.id
    after = new.model_dump()
    if audit_group is not None:
        before, after = before[audit_group], after[audit_group]
    await audit.record(
        db, action, "settings", "runtime",
        actor_user_id=actor.id, before=before, after=after,
    )  # fmt: skip
    await db.commit()
    reset_cache()
    return row
