"""Stored settings: partial storage, merging, stale versions, audit, fallback."""

from collections.abc import Callable

import pytest
from sqlalchemy import select

import app_settings
from app_settings import StaleSettingsError, load, runtime, save
from database.models import AuditEvent, Role, User
from database.session import sync_session

pytestmark = pytest.mark.db


def admin(create_user: Callable[..., User]) -> User:
    user: User = create_user(Role.ADMIN)
    return user


async def test_nothing_stored_means_defaults(clean_db: None) -> None:
    assert runtime() == app_settings.defaults()


async def test_save_stores_only_changes_and_is_audited(create_user, async_db) -> None:  # type: ignore[no-untyped-def]
    new = app_settings.defaults()
    new.email.mailbox_check_seconds = 120
    row = await save(async_db, new, actor=admin(create_user), expected_version=0)
    assert row.version == 1
    assert row.data == {"email": {"mailbox_check_seconds": 120}}
    assert runtime().email.mailbox_check_seconds == 120  # cache reset on save
    with sync_session() as db:
        event = db.scalars(select(AuditEvent).where(AuditEvent.action == "settings.updated")).one()
        assert event.before is not None and event.after is not None
        assert event.before["email"]["mailbox_check_seconds"] == 60
        assert event.after["email"]["mailbox_check_seconds"] == 120


async def test_stale_version_is_refused(create_user, async_db) -> None:  # type: ignore[no-untyped-def]
    user = admin(create_user)
    await save(async_db, app_settings.defaults(), actor=user, expected_version=0)
    with pytest.raises(StaleSettingsError):
        await save(async_db, app_settings.defaults(), actor=user, expected_version=0)


def test_unknown_stored_keys_are_ignored() -> None:
    loaded = load({"email": {"mailbox_check_seconds": 90, "retired_option": 1}, "old_group": {}})
    assert loaded.email.mailbox_check_seconds == 90


def test_invalid_stored_values_fall_back_to_defaults() -> None:
    assert load({"email": {"mailbox_check_seconds": 5}}) == app_settings.defaults()


async def test_unreadable_table_falls_back(clean_db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from app_settings import store

    def broken() -> None:
        raise RuntimeError("database down")

    monkeypatch.setattr(store, "sync_session", broken)
    assert runtime() == app_settings.defaults()
