# Admin Settings and Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Administrators change e-mail timing, AI behaviour, review thresholds, SLA timing and
the shop/console branding from a Settings page, with no redeploy.

**Architecture:** A new `app_settings` package holds a validated `RuntimeSettings` document
(defaults = today's env/config values; only changed fields stored in a one-row
`app_settings` table), read through `runtime()` with a 15-second cache. Consumers read
`runtime()` instead of env/config. Celery Beat runs one `tick` every 15 s; a `job_runs` table
gates each periodic job to its configured interval. Logos are content-checked images in
storage, served publicly; the web reads `GET /branding`.

**Tech Stack:** FastAPI, SQLAlchemy 2 (sync + async), Alembic, Pydantic 2, Celery, pytest
(real PostgreSQL), Next.js 16 app router, TanStack Query, generated `@hey-api` client, shadcn/ui.

**Spec:** `docs/superpowers/specs/2026-09-28-admin-settings-design.md`

## Global Constraints

- Secrets (API keys, passwords, database/Redis URLs) are never stored in or returned by Settings.
- Defaults equal today's behaviour: mailbox 60 s, outbox 30 s, `MAIL_FROM_NAME`, auto replies on, `GENAI_PROVIDER`/model/`GENAI_EFFORT`, retrieval 8, auto analysis on, SLA scan from `analytics.yaml` (5 min), `verified_min_score` 80, `always_review_escalation_level` 4, company details from `config/storefront.yaml`, console name "SupportNova", no logos.
- Limits: mailbox 60–3600 s; outbox 15–600 s; from_name 1–80; model 1–100; retrieval 3–20; SLA scan 1–60 min; verified score 50–100; review level 1–5; shop_name 1–60; tagline 0–140; console_name 1–40; phone 1–40; address 1–200; hours 1–100; support_email ≤ 120 and valid.
- All text settings are single-line (no control characters, no CR/LF): they reach e-mail headers.
- Policy numbers (warranty, returns, delivery) are read-only in Settings.
- Logos: PNG, JPEG or WebP only, ≤ 1 MB, type from file content; SVG refused.
- Every save is audited (`settings.updated`, before/after); stale `version` → 409.
- Python: ruff, ruff format, `mypy --strict` clean. Web: ESLint, `tsc`, `next build` clean.
- Commits: signed as the repo's configured user; no `Co-Authored-By` line (Vercel Hobby blocks it).

## Review Focus

- Stored settings from an older version contain a key that no longer exists → ignored, the rest still applies (test in Task 2).
- Stored settings no longer pass validation (limits tightened) → defaults are used and a warning logged, the system keeps working (test in Task 2).
- `from_name` with a line break (e-mail header injection) → rejected with 422 (test in Task 1).
- Provider switched while the model is the other provider's model (e.g. `openai` + `claude-opus-5`) → rejected with a clear message (test in Task 1).
- A job that raises inside `tick` → the other due jobs still run, and the failing job waits for its next interval instead of retrying every 15 s (test in Task 6).

---

## File Structure

| File | Responsibility |
|---|---|
| `app_settings/__init__.py` | Public API: `RuntimeSettings`, `defaults`, `runtime`, `override`, `reset_cache`, `save`, `StaleSettingsError` |
| `app_settings/model.py` | `RuntimeSettings` and group models, limits, validators, `SUGGESTED_MODELS` |
| `app_settings/defaults.py` | `defaults()` from env and config files |
| `app_settings/store.py` | Load/merge/cache, `runtime()`, `override()`, `save()` |
| `app_settings/facts.py` | Read-only policy facts with source documents |
| `app_settings/logos.py` | Logo checks, storage keys, set/remove |
| `app_settings/jobs.py` | `claim()` gate and `tick()` |
| `app_settings/tasks.py` | Celery task wrapping `tick()` |
| `database/models/settings.py` | `AppSettingsRow`, `JobRun` |
| `database/migrations/versions/20260928_*_app_settings.py` | Tables |
| `src/api/routes/settings.py` | Settings and branding endpoints |
| `src/api/schemas.py` | `SettingsOut`, `SettingsUpdate`, `BrandingOut`, `PolicyFactOut` |
| `tests/fixtures/settings.py` | `use_settings()` test helper |
| `web/src/components/settings/settings-manager.tsx` | Settings page tabs and forms |
| `web/src/components/settings/logo-upload.tsx` | Logo upload/remove |
| `web/src/lib/branding.ts` | `useBranding()` and `BrandMark` |

---

### Task 1: Settings model and defaults

**Files:**
- Create: `app_settings/__init__.py`, `app_settings/model.py`, `app_settings/defaults.py`
- Test: `tests/unit/test_app_settings_model.py`

**Interfaces:**
- Produces: `RuntimeSettings(email: EmailSettings, ai: AiSettings, operations: OperationsSettings, branding: BrandingSettings)`; `BrandingText` (branding without logo keys); `SUGGESTED_MODELS: dict[str, list[str]]`; `defaults() -> RuntimeSettings`.

- [ ] **Step 1: Write the failing tests**

```python
"""Runtime settings: defaults equal today's behaviour; limits and single-line text."""

import pytest
from pydantic import ValidationError

from app_settings import RuntimeSettings, defaults


def test_defaults_are_todays_behaviour() -> None:
    d = defaults()
    assert (d.email.mailbox_check_seconds, d.email.outbox_flush_seconds) == (60, 30)
    assert d.email.auto_replies and d.ai.auto_analysis
    assert d.ai.retrieval_limit == 8
    assert (d.operations.sla_scan_minutes, d.operations.verified_min_score) == (5, 80)
    assert d.operations.always_review_escalation_level == 4
    assert d.branding.shop_name == "VoltHaven Electronics"
    assert d.branding.console_name == "SupportNova"
    assert d.branding.shop_logo_key is None and d.branding.console_logo_key is None


def with_group(group: str, **values: object) -> dict[str, object]:
    data = defaults().model_dump()
    data[group] = {**data[group], **values}  # type: ignore[dict-item]
    return data


@pytest.mark.parametrize(
    ("group", "field", "value"),
    [
        ("email", "mailbox_check_seconds", 59),
        ("email", "outbox_flush_seconds", 601),
        ("ai", "retrieval_limit", 21),
        ("operations", "verified_min_score", 49),
        ("operations", "always_review_escalation_level", 6),
        ("branding", "shop_name", ""),
        ("branding", "support_email", "not-an-email"),
    ],
)
def test_out_of_range_values_are_rejected(group: str, field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        RuntimeSettings.model_validate(with_group(group, **{field: value}))


def test_text_must_be_one_line() -> None:  # from_name reaches the e-mail From header
    with pytest.raises(ValidationError):
        RuntimeSettings.model_validate(with_group("email", from_name="Care\r\nBcc: x@y.z"))


def test_model_must_belong_to_the_provider() -> None:
    with pytest.raises(ValidationError, match="Anthropic model"):
        RuntimeSettings.model_validate(with_group("ai", provider="openai", model="claude-opus-5"))
    ok = RuntimeSettings.model_validate(with_group("ai", provider="openai", model="gpt-5"))
    assert ok.ai.model == "gpt-5"


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        RuntimeSettings.model_validate(with_group("email", password="x"))
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest -q tests/unit/test_app_settings_model.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'app_settings'`.

- [ ] **Step 3: Implement `app_settings/model.py`**

```python
"""Settings administrators change at run time (the staff Settings page)."""

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

Provider = Literal["openai", "anthropic"]
Effort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]
LogoTarget = Literal["shop", "console"]

SUGGESTED_MODELS: dict[str, list[str]] = {
    "openai": ["gpt-5-mini", "gpt-5", "gpt-5-nano"],
    "anthropic": ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"],
}
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _one_line(value: str) -> str:
    if _CONTROL.search(value):
        raise ValueError("must be a single line of text")
    return value.strip()


def _email(value: str) -> str:
    if not _EMAIL.match(value):
        raise ValueError("must be an e-mail address")
    return value


Line = Annotated[str, AfterValidator(_one_line)]


class _Group(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmailSettings(_Group):
    mailbox_check_seconds: int = Field(ge=60, le=3600)
    outbox_flush_seconds: int = Field(ge=15, le=600)
    from_name: Annotated[Line, Field(min_length=1, max_length=80)]
    auto_replies: bool


class AiSettings(_Group):
    provider: Provider
    model: Annotated[Line, Field(min_length=1, max_length=100)]
    effort: Effort
    retrieval_limit: int = Field(ge=3, le=20)
    auto_analysis: bool

    @model_validator(mode="after")
    def _model_matches_provider(self) -> "AiSettings":
        other = "anthropic" if self.provider == "openai" else "openai"
        if self.model in SUGGESTED_MODELS[other]:
            label = "an Anthropic" if other == "anthropic" else "an OpenAI"
            raise ValueError(f"{self.model} is {label} model; choose one for {self.provider}")
        return self


class OperationsSettings(_Group):
    sla_scan_minutes: int = Field(ge=1, le=60)
    verified_min_score: int = Field(ge=50, le=100)
    always_review_escalation_level: int = Field(ge=1, le=5)


class BrandingText(_Group):
    shop_name: Annotated[Line, Field(min_length=1, max_length=60)]
    shop_tagline: Annotated[Line, Field(max_length=140)]
    console_name: Annotated[Line, Field(min_length=1, max_length=40)]
    support_email: Annotated[Line, Field(max_length=120), AfterValidator(_email)]
    phone: Annotated[Line, Field(min_length=1, max_length=40)]
    address: Annotated[Line, Field(min_length=1, max_length=200)]
    hours: Annotated[Line, Field(min_length=1, max_length=100)]


class BrandingSettings(BrandingText):
    shop_logo_key: str | None = None  # set only by the logo upload
    console_logo_key: str | None = None


class RuntimeSettings(_Group):
    email: EmailSettings
    ai: AiSettings
    operations: OperationsSettings
    branding: BrandingSettings
```

- [ ] **Step 4: Implement `app_settings/defaults.py`**

```python
"""Today's behaviour, from environment variables and config files: the settings defaults."""

from app_settings.model import RuntimeSettings


def defaults() -> RuntimeSettings:
    # Local imports: these modules import app_settings for their own settings.
    from python_validation.types import validation_config
    from src.core.config import get_settings
    from src.core.domain import analytics_config
    from storefront.config import storefront_config

    env, validation, company = get_settings(), validation_config(), storefront_config().company
    return RuntimeSettings.model_validate(
        {
            "email": {
                "mailbox_check_seconds": 60,
                "outbox_flush_seconds": 30,
                "from_name": env.mail_from_name,
                "auto_replies": True,
            },
            "ai": {
                "provider": env.genai_provider,
                "model": env.genai_model,
                "effort": env.genai_effort,
                "retrieval_limit": env.retrieval_limit,
                "auto_analysis": True,
            },
            "operations": {
                "sla_scan_minutes": analytics_config()["sla"]["scan_interval_minutes"],
                "verified_min_score": validation["verified_min_score"],
                "always_review_escalation_level": validation["always_review_escalation_level"],
            },
            "branding": {
                "shop_name": company.name,
                "shop_tagline": company.tagline,
                "console_name": "SupportNova",
                "support_email": company.support_email,
                "phone": company.phone,
                "address": company.address,
                "hours": company.hours,
            },
        }
    )
```

- [ ] **Step 5: Implement `app_settings/__init__.py` (Task 2 adds the store exports)**

```python
"""Settings administrators change at run time, without redeploying."""

from app_settings.defaults import defaults
from app_settings.model import SUGGESTED_MODELS, BrandingText, RuntimeSettings

__all__ = ["SUGGESTED_MODELS", "BrandingText", "RuntimeSettings", "defaults"]
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest -q tests/unit/test_app_settings_model.py`
Expected: PASS (all).

- [ ] **Step 7: Commit**

```bash
git add app_settings tests/unit/test_app_settings_model.py
git commit -m "feat(settings): runtime settings model and defaults"
```

---

### Task 2: Storage, cache and save

**Files:**
- Create: `database/models/settings.py`, `app_settings/store.py`, migration, `tests/fixtures/settings.py`
- Modify: `database/models/__init__.py`, `app_settings/__init__.py`, `tests/conftest.py`
- Test: `tests/integration/test_app_settings_store.py`

**Interfaces:**
- Consumes: `RuntimeSettings`, `defaults()` (Task 1).
- Produces: `runtime() -> RuntimeSettings`; `override(settings: RuntimeSettings | None) -> None`; `reset_cache() -> None`; `load(data: dict | None) -> RuntimeSettings`; `async save(db: AsyncSession, new: RuntimeSettings, *, actor: User, expected_version: int | None) -> AppSettingsRow`; `StaleSettingsError`; `async current_row(db) -> AppSettingsRow | None`; models `AppSettingsRow(id, data, version, updated_at, updated_by_id)`, `JobRun(job, last_run_at)`; test helper `use_settings(**groups) -> RuntimeSettings`.

- [ ] **Step 1: Models `database/models/settings.py`**

```python
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
```

Add to `database/models/__init__.py` imports and `__all__`: `from database.models.settings import AppSettingsRow, JobRun`.

- [ ] **Step 2: Migration**

Run: `uv run alembic revision --autogenerate -m "app settings and job runs"`, then rename the file to
`database/migrations/versions/20260928_<rev>_app_settings.py` (matching the existing naming) and
check it creates exactly `app_settings` (id, data JSONB, version, updated_at, updated_by_id FK
users.id) and `job_runs` (job PK, last_run_at). `down_revision` must be `ebc044fd7154`.
Run: `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`
Expected: no errors.

- [ ] **Step 3: Test helper `tests/fixtures/settings.py` and conftest fixture**

```python
"""Run tests with specific runtime settings."""

import app_settings
from app_settings import RuntimeSettings


def use_settings(**groups: dict[str, object]) -> RuntimeSettings:
    """E.g. use_settings(email={"auto_replies": False}); reset after each test by conftest."""
    base = app_settings.defaults()
    updated = base.model_copy(
        update={name: getattr(base, name).model_copy(update=values) for name, values in groups.items()}
    )
    app_settings.override(updated)
    return updated
```

Add to `tests/conftest.py` (after the imports block):

```python
@pytest.fixture(autouse=True)
def _runtime_settings(request: pytest.FixtureRequest) -> Iterator[None]:
    """Tests without a database use the defaults; database tests read the (empty) table."""
    import app_settings

    app_settings.reset_cache()
    if request.node.get_closest_marker("db") is None:
        app_settings.override(app_settings.defaults())
    yield
    app_settings.override(None)
    app_settings.reset_cache()
```

- [ ] **Step 4: Write the failing tests `tests/integration/test_app_settings_store.py`**

```python
"""Stored settings: partial storage, merging, stale versions, audit, fallback."""

import pytest
from sqlalchemy import select

import app_settings
from app_settings import StaleSettingsError, load, runtime, save
from database.models import AppSettingsRow, AuditEvent, Role, User
from database.session import sync_session

pytestmark = pytest.mark.db


def admin(create_user) -> User:  # type: ignore[no-untyped-def]
    return create_user(Role.ADMIN)


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
```

`async_db` fixture — add to `tests/conftest.py` if it does not exist (check with `grep -n "def async_db" tests/conftest.py`):

```python
@pytest.fixture
async def async_db(clean_db: None) -> AsyncIterator[AsyncSession]:
    from database.session import async_session_factory

    async with async_session_factory()() as session:
        yield session
```

(`AsyncIterator` from `collections.abc`, `AsyncSession` from `sqlalchemy.ext.asyncio`.)

- [ ] **Step 5: Run to verify failure**

Run: `uv run pytest -q tests/integration/test_app_settings_store.py`
Expected: FAIL — `ImportError: cannot import name 'StaleSettingsError'`.

- [ ] **Step 6: Implement `app_settings/store.py`**

```python
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
    """Defaults with the stored changes on top; unknown keys ignored; invalid → defaults."""
    base = defaults().model_dump()
    stored = data or {}
    merged = {
        group: {
            **fields,
            **{k: v for k, v in (stored.get(group) or {}).items() if k in fields},
        }
        for group, fields in base.items()
    }
    try:
        return RuntimeSettings.model_validate(merged)
    except ValidationError as exc:
        log.warning("settings.invalid_stored", error=str(exc)[:500])
        return RuntimeSettings.model_validate(base)


def override(settings: RuntimeSettings | None) -> None:
    """Tests: use these settings instead of the database (None to stop)."""
    global _override
    _override = settings


def reset_cache() -> None:
    global _cache
    _cache = None


def runtime() -> RuntimeSettings:
    """Current settings, re-read from the database at most every 15 seconds."""
    global _cache
    if _override is not None:
        return _override
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < CACHE_SECONDS:
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
    db: AsyncSession, new: RuntimeSettings, *, actor: User, expected_version: int | None
) -> AppSettingsRow:
    """Store the changes from the defaults; `expected_version=None` skips the stale check."""
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
    await audit.record(
        db, "settings.updated", "settings", "runtime",
        actor_user_id=actor.id, before=before, after=new.model_dump(),
    )  # fmt: skip
    await db.commit()
    reset_cache()
    return row
```

Update `app_settings/__init__.py`:

```python
"""Settings administrators change at run time, without redeploying."""

from app_settings.defaults import defaults
from app_settings.model import SUGGESTED_MODELS, BrandingText, RuntimeSettings
from app_settings.store import (
    StaleSettingsError,
    current_row,
    load,
    override,
    reset_cache,
    runtime,
    save,
)

__all__ = [
    "SUGGESTED_MODELS",
    "BrandingText",
    "RuntimeSettings",
    "StaleSettingsError",
    "current_row",
    "defaults",
    "load",
    "override",
    "reset_cache",
    "runtime",
    "save",
]
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest -q tests/integration/test_app_settings_store.py tests/unit/test_app_settings_model.py`
Expected: PASS. If `audit.record` signature differs (`entity_id` type), adjust the call, not the test.

- [ ] **Step 8: Full suite and commit**

Run: `uv run pytest -q` — Expected: all pass (the autouse fixture keeps unit tests off the database).

```bash
git add app_settings database tests
git commit -m "feat(settings): stored run-time settings with cache, audit and stale check"
```

---

### Task 3: Settings API (read and save)

**Files:**
- Create: `src/api/routes/settings.py`, `app_settings/facts.py`
- Modify: `src/api/schemas.py`, `src/main.py` (include router like the others), `src/core/config.py`
- Test: `tests/integration/test_settings_api.py`

**Interfaces:**
- Consumes: `runtime`, `save`, `StaleSettingsError`, `SUGGESTED_MODELS`, `current_row` (Tasks 1–2).
- Produces: `GET /api/v1/settings` → `SettingsOut`; `PUT /api/v1/settings` (body `SettingsUpdate`) → `SettingsOut`; `Settings.api_key_for(provider: str) -> str | None`; `policy_facts(db) -> list[PolicyFactOut]`.

- [ ] **Step 1: Write the failing tests**

```python
"""Settings API: admin only, version check, provider keys, no secrets."""

from collections.abc import Callable

import httpx
import pytest

from database.models import Role

pytestmark = pytest.mark.db
URL = "/api/v1/settings"


def body(current: dict, **group_changes: dict) -> dict:  # type: ignore[type-arg]
    s = current["settings"]
    update = {g: {**s[g], **group_changes.get(g, {})} for g in ("email", "ai", "operations")}
    branding = {k: v for k, v in s["branding"].items() if not k.endswith("_logo_key")}
    return {"version": current["version"], **update, "branding": {**branding, **group_changes.get("branding", {})}}


async def test_admin_reads_and_saves(client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]) -> None:
    admin = auth_headers(Role.ADMIN)
    current = (await client.get(URL, headers=admin)).json()
    assert current["version"] == 0 and current["settings"]["email"]["mailbox_check_seconds"] == 60
    assert "openai" in current["suggested_models"]
    assert {f["source"] for f in current["policy_facts"]} >= {"WAR-POL-02", "REF-POL-01", "DEL-POL-04"}
    saved = await client.put(URL, headers=admin, json=body(current, email={"mailbox_check_seconds": 300}))
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 1
    assert saved.json()["settings"]["email"]["mailbox_check_seconds"] == 300


async def test_stale_version_conflicts(client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]) -> None:
    admin = auth_headers(Role.ADMIN)
    current = (await client.get(URL, headers=admin)).json()
    assert (await client.put(URL, headers=admin, json=body(current))).status_code == 200
    assert (await client.put(URL, headers=admin, json=body(current))).status_code == 409


async def test_provider_without_key_is_refused(client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    from src.core.config import get_settings

    get_settings.cache_clear()
    admin = auth_headers(Role.ADMIN)
    current = (await client.get(URL, headers=admin)).json()
    response = await client.put(URL, headers=admin, json=body(current, ai={"provider": "anthropic", "model": "claude-opus-5"}))
    assert response.status_code == 422 and "ANTHROPIC_API_KEY" in response.text
    get_settings.cache_clear()


async def test_staff_who_are_not_admins_cannot_see_settings(client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]) -> None:
    for role in (Role.AGENT, Role.MANAGER, Role.CUSTOMER):
        assert (await client.get(URL, headers=auth_headers(role))).status_code == 403


async def test_no_secret_is_ever_returned(client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]) -> None:
    text = (await client.get(URL, headers=auth_headers(Role.ADMIN))).text.lower()
    for word in ("api_key", "password", "database_url", "redis_url", "secret"):
        assert word not in text
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest -q tests/integration/test_settings_api.py`
Expected: FAIL — 404 on `/api/v1/settings`.

- [ ] **Step 3: `Settings.api_key_for` in `src/core/config.py`** (next to `genai_api_key`)

```python
    def api_key_for(self, provider: str) -> str | None:
        return self.openai_api_key if provider == "openai" else self.anthropic_api_key
```

- [ ] **Step 4: Schemas in `src/api/schemas.py`**

```python
class PolicyFactOut(BaseModel):
    fact: str
    value: str
    source: str  # document code
    version: str | None  # active version, None if the document is not active


class SettingsOut(BaseModel):
    settings: RuntimeSettings
    version: int
    updated_at: datetime | None
    updated_by: str | None
    providers_available: list[str]
    suggested_models: dict[str, list[str]]
    policy_facts: list[PolicyFactOut]
    shop_logo_url: str | None
    console_logo_url: str | None


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    email: EmailSettings
    ai: AiSettings
    operations: OperationsSettings
    branding: BrandingText
```

(import `RuntimeSettings, EmailSettings, AiSettings, OperationsSettings, BrandingText` from `app_settings.model`; `ConfigDict`, `datetime` if not already imported.)

- [ ] **Step 5: `app_settings/facts.py`**

```python
"""Policy numbers shown read-only in Settings, with the document they come from."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Document, DocumentVersion, VersionStatus
from src.api.schemas import PolicyFactOut
from storefront.config import storefront_config


async def policy_facts(db: AsyncSession) -> list[PolicyFactOut]:
    c = storefront_config()
    rows = [
        ("Warranty", f"{c.warranty.months} months (VoltCare+ {c.warranty.extended_months})", "WAR-POL-02"),
        ("Return window", f"{c.returns.window_days} days from delivery", "REF-POL-01"),
        ("Refund time", f"{c.returns.refund_min_days}–{c.returns.refund_max_days} business days", "REF-POL-01"),
        ("Standard delivery", f"{c.shipping.standard_days} business days", "DEL-POL-04"),
        ("Express delivery", f"{c.shipping.express_days} business days", "DEL-POL-04"),
        ("Late-delivery credit", f"{c.shipping.late_credit_pct}% up to USD {c.shipping.late_credit_cap_usd}", "DEL-POL-04"),
    ]
    active = dict(
        (
            await db.execute(
                select(Document.doc_code, DocumentVersion.version)
                .join(DocumentVersion, DocumentVersion.document_id == Document.id)
                .where(DocumentVersion.status == VersionStatus.ACTIVE)
            )
        ).tuples().all()
    )
    return [PolicyFactOut(fact=f, value=v, source=s, version=active.get(s)) for f, v, s in rows]
```

- [ ] **Step 6: Routes `src/api/routes/settings.py`**

```python
"""Run-time settings (admin) and public branding."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import app_settings
from app_settings import SUGGESTED_MODELS, RuntimeSettings, StaleSettingsError
from app_settings.facts import policy_facts
from database.models import Role, User
from database.session import get_db
from security.dependencies import require_roles
from src.api.schemas import SettingsOut, SettingsUpdate
from src.core.config import get_settings

router = APIRouter(tags=["settings"])
admin_only = require_roles(Role.ADMIN)


def logo_url(target: str, key: str | None) -> str | None:
    """Relative to the API host; the key in the query string busts caches after a change."""
    return f"/api/v1/branding/logo/{target}?v={key.rsplit('-', 1)[-1]}" if key else None


async def _out(db: AsyncSession) -> SettingsOut:
    row = await app_settings.current_row(db)
    current = app_settings.load(row.data if row else None)
    who = await db.get(User, row.updated_by_id) if row and row.updated_by_id else None
    env = get_settings()
    return SettingsOut(
        settings=current,
        version=row.version if row else 0,
        updated_at=row.updated_at if row else None,
        updated_by=(who.full_name or who.email) if who else None,
        providers_available=[p for p in ("openai", "anthropic") if env.api_key_for(p)],
        suggested_models=SUGGESTED_MODELS,
        policy_facts=await policy_facts(db),
        shop_logo_url=logo_url("shop", current.branding.shop_logo_key),
        console_logo_url=logo_url("console", current.branding.console_logo_key),
    )


@router.get("/settings", response_model=SettingsOut)
async def read_settings(_: User = Depends(admin_only), db: AsyncSession = Depends(get_db)) -> SettingsOut:
    return await _out(db)


@router.put("/settings", response_model=SettingsOut)
async def update_settings(
    payload: SettingsUpdate, actor: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> SettingsOut:
    if not get_settings().api_key_for(payload.ai.provider):
        name = "OPENAI_API_KEY" if payload.ai.provider == "openai" else "ANTHROPIC_API_KEY"
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Add {name} on the server first."
        )
    row = await app_settings.current_row(db)
    logos = app_settings.load(row.data if row else None).branding  # logos are set by upload only
    new = RuntimeSettings(
        email=payload.email,
        ai=payload.ai,
        operations=payload.operations,
        branding={**payload.branding.model_dump(), "shop_logo_key": logos.shop_logo_key,
                  "console_logo_key": logos.console_logo_key},  # type: ignore[arg-type]
    )  # fmt: skip
    try:
        await app_settings.save(db, new, actor=actor, expected_version=payload.version)
    except StaleSettingsError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Someone else changed the settings; reload and try again."
        ) from exc
    return await _out(db)
```

Register in `src/main.py` next to the other routers (`from src.api.routes import settings` and add it to the list passed to `include_router` with `prefix=settings.api_prefix`; follow the existing loop).

- [ ] **Step 7: Run tests**

Run: `uv run pytest -q tests/integration/test_settings_api.py`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add app_settings src tests/integration/test_settings_api.py
git commit -m "feat(settings): admin API to read and save settings"
```

---

### Task 4: AI and analysis settings take effect

**Files:**
- Modify: `genai_pipeline/providers.py`, `genai_pipeline/pipeline.py:87`, `genai_pipeline/evidence.py:68-70`, `genai_pipeline/analyze.py:50-53`, `python_validation/checks.py:131`, `complaint_processing/service.py`, `support_chat/service.py:387`, `email_channel/inbound.py:210`, `bulk_import/service.py:203`
- Modify test: `tests/unit/test_openai_provider.py:175-191`
- Test: `tests/unit/test_runtime_ai_settings.py`, `tests/integration/test_auto_analysis_setting.py`

**Interfaces:**
- Consumes: `runtime()`, `use_settings()`.
- Produces: `get_provider() -> LLMProvider` (built from `runtime().ai`, cached per provider/model/effort); `enqueue_automatic(complaint_id, triggered_by=None) -> bool`.

- [ ] **Step 1: Failing unit tests `tests/unit/test_runtime_ai_settings.py`**

```python
"""AI settings from the Settings page reach the provider, retrieval and verdicts."""

import pytest

from genai_pipeline.providers import get_provider
from src.core.config import Settings
from tests.fixtures.settings import use_settings


def test_provider_and_model_come_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "genai_pipeline.providers.get_settings",
        lambda: Settings(openai_api_key="sk-test", anthropic_api_key="ak-test"),
    )
    use_settings(ai={"provider": "openai", "model": "gpt-5", "effort": "minimal"})
    provider = get_provider()
    assert (provider.name, provider.model) == ("openai", "gpt-5")
    use_settings(ai={"provider": "anthropic", "model": "claude-sonnet-5", "effort": "low"})
    assert (get_provider().name, get_provider().model) == ("anthropic", "claude-sonnet-5")


def test_review_thresholds_come_from_settings() -> None:
    from python_validation.checks import verdict_config

    use_settings(operations={"verified_min_score": 95, "always_review_escalation_level": 2})
    cfg = verdict_config()
    assert (cfg["verified_min_score"], cfg["always_review_escalation_level"]) == (95, 2)
```

Replace `test_provider_is_chosen_by_one_setting` in `tests/unit/test_openai_provider.py` with:

```python
def test_provider_is_chosen_by_one_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(genai_provider="openai", openai_api_key="sk-test", openai_model="gpt-x")
    assert (settings.genai_model, settings.genai_api_key_name) == ("gpt-x", "OPENAI_API_KEY")
    monkeypatch.setattr("genai_pipeline.providers.get_settings", lambda: settings)
    use_settings(ai={"provider": "openai", "model": "gpt-x"})
    provider = get_provider()
    assert (provider.name, provider.model) == ("openai", "gpt-x")
    claude = Settings(genai_provider="anthropic", anthropic_model="claude-opus-5")
    assert (claude.genai_model, claude.genai_api_key_name) == ("claude-opus-5", "ANTHROPIC_API_KEY")
```

(add `from tests.fixtures.settings import use_settings`.)

- [ ] **Step 2: Failing integration test `tests/integration/test_auto_analysis_setting.py`**

```python
"""'Analyse new complaints automatically' off: intake queues nothing; a manual re-run still does."""

from collections.abc import Callable

import httpx
import pytest

from database.models import Role
from tests.fixtures.settings import use_settings

pytestmark = pytest.mark.db

COMPLAINT = {
    "title": "Charger stopped working",
    "description": "My VoltCharge 65W charger stopped working after two days of normal use.",
    "requested_resolution": "A replacement",
}


async def test_auto_analysis_off_queues_nothing_until_asked(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    use_settings(ai={"auto_analysis": False})
    customer = auth_headers(Role.CUSTOMER)
    created = await client.post("/api/v1/complaints", json=COMPLAINT, headers=customer)
    assert created.status_code == 201, created.text
    assert client.app.state.analyses == []  # type: ignore[attr-defined]
    ref = created.json()["complaint_ref"]
    rerun = await client.post(f"/api/v1/complaints/{ref}/analyze", headers=auth_headers(Role.AGENT))
    assert rerun.status_code == 202
    assert len(client.app.state.analyses) == 1  # type: ignore[attr-defined]
```

(`ComplaintCreate` requires only `title` and `description`.)

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest -q tests/unit/test_runtime_ai_settings.py tests/integration/test_auto_analysis_setting.py`
Expected: FAIL (`verdict_config` missing; analysis queued although off).

- [ ] **Step 4: Provider from settings (`genai_pipeline/providers.py`)**

Replace `get_provider`:

```python
def get_provider() -> LLMProvider:
    """The provider and model chosen on the Settings page; keys stay in the environment."""
    ai = app_settings.runtime().ai
    return _build_provider(ai.provider, ai.model, ai.effort)


@lru_cache(maxsize=4)
def _build_provider(provider: str, model: str, effort: str) -> LLMProvider:
    settings = get_settings()
    if provider == "anthropic":
        return AnthropicProvider(
            model=model, effort=effort, timeout_seconds=settings.genai_timeout_seconds,
            api_key=settings.anthropic_api_key,
        )  # fmt: skip
    if provider == "openai":
        return OpenAIProvider(
            model=model, effort=effort, timeout_seconds=settings.genai_timeout_seconds,
            api_key=settings.openai_api_key, reasoning=settings.openai_reasoning,
        )  # fmt: skip
    raise ProviderRequestError(f"Unsupported GenAI provider: {provider}")
```

Add `import app_settings`. Search for other `get_provider.cache_clear()` callers: `grep -rn "get_provider.cache_clear" --include=*.py .` and change them to `_build_provider.cache_clear()` (tests that patch `get_settings` must clear it).

- [ ] **Step 5: Retrieval limit, evidence, analyze CLI**

- `genai_pipeline/pipeline.py:87`: `settings.retrieval_limit` → `app_settings.runtime().ai.retrieval_limit` (add `import app_settings`).
- `genai_pipeline/evidence.py:68-70`: record `app_settings.runtime().ai.provider`, `.model`, `.effort` instead of the env values.
- `genai_pipeline/analyze.py:50-53`: replace the key check with
  ```python
  ai = app_settings.runtime().ai
  if not settings.api_key_for(ai.provider):
      print(f"No API key for {ai.provider} (set it in .env or on the server)")
      return 1
  ```

- [ ] **Step 6: Thresholds (`python_validation/checks.py`)**

Add above the function containing line 131 and use it there (`cfg = verdict_config()`):

```python
def verdict_config() -> dict[str, Any]:
    """validation.yaml with the two review thresholds from the Settings page."""
    ops = app_settings.runtime().operations
    return {
        **validation_config(),
        "verified_min_score": ops.verified_min_score,
        "always_review_escalation_level": ops.always_review_escalation_level,
    }
```

- [ ] **Step 7: Automatic analysis (`complaint_processing/service.py`)**

After `safe_enqueue_analysis` add:

```python
def enqueue_automatic(complaint_id: uuid.UUID, triggered_by: uuid.UUID | None = None) -> bool:
    """Analysis started by intake (web, chat, e-mail, bulk import), unless switched off."""
    if not app_settings.runtime().ai.auto_analysis:
        log.info("analysis.automatic_off", complaint_id=str(complaint_id))
        return False
    safe_enqueue_analysis(complaint_id, triggered_by)
    return True
```

Replace `safe_enqueue_analysis(` with `enqueue_automatic(` at: `complaint_processing/service.py:282`,
`support_chat/service.py:387`, `email_channel/inbound.py:210`, `bulk_import/service.py:203`
(update their imports). Leave `complaint_processing/review.py:275` and
`src/api/routes/complaints.py:296` (manual) unchanged.

- [ ] **Step 8: Run tests**

Run: `uv run pytest -q tests/unit/test_runtime_ai_settings.py tests/unit/test_openai_provider.py tests/integration/test_auto_analysis_setting.py && uv run pytest -q`
Expected: PASS, full suite green.

- [ ] **Step 9: Commit**

```bash
git add genai_pipeline python_validation complaint_processing support_chat email_channel bulk_import tests
git commit -m "feat(settings): AI provider, model, effort, retrieval, thresholds and auto-analysis from Settings"
```

---

### Task 5: E-mail sender name and automatic replies

**Files:**
- Modify: `email_channel/tasks.py:136`, `email_channel/transport.py` (`BrevoSender.send`), `python_validation/pipeline.py` (`_apply`), `email_channel/notify.py`, `support_chat/notify.py`
- Test: `tests/unit/test_auto_replies_setting.py`, `tests/integration/test_auto_replies_setting.py`

**Interfaces:**
- Consumes: `runtime()`, `use_settings()`.
- Produces: `after_validation(db, complaint, verdict, draft, *, auto_reply: bool = True)` in both notify modules; in `python_validation/pipeline.py`: `AUTO_REPLIES_OFF = "Automatic replies are off: approve the reply."` and `review_reasons(verdict: str, reasons: list[str], *, auto_replies: bool) -> list[str] | None`.

- [ ] **Step 1: Failing unit tests `tests/unit/test_auto_replies_setting.py`**

```python
"""Automatic replies off: verified complaints wait for a reviewer; sender name from Settings."""

from database.models import OutboundEmail
from email_channel.tasks import build_message
from python_validation.pipeline import AUTO_REPLIES_OFF, review_reasons
from src.core.config import get_settings
from tests.fixtures.settings import use_settings


def test_review_reasons_follow_the_setting() -> None:
    assert review_reasons("verified", [], auto_replies=True) is None
    assert review_reasons("corrected", ["fixed priority"], auto_replies=True) is None
    assert review_reasons("verified", [], auto_replies=False) == [AUTO_REPLIES_OFF]
    assert review_reasons("needs_review", ["unsupported promise"], auto_replies=False) == [
        "unsupported promise"
    ]


def test_sender_name_comes_from_settings() -> None:
    use_settings(email={"from_name": "Nova Support Desk"})
    email = OutboundEmail(
        to_address="sara@example.test",
        kind="reply",
        subject="Re: Cracked screen [CMP-000001]",
        body="Hello",
        message_id="<m1@volthaven.test>",
    )
    assert build_message(email, get_settings())["From"].startswith("Nova Support Desk")
```

- [ ] **Step 2: Failing integration tests `tests/integration/test_auto_replies_setting.py`**

```python
"""The e-mail and chat hooks send a holding message instead of the reply when told to."""

import json
from collections.abc import Callable

import httpx
import pytest
from sqlalchemy import select

from database.models import ChatMessage, Complaint, InboundEmail, OutboundEmail, Role, User
from database.session import async_session_factory, sync_session
from email_channel.inbound import process_email
from email_channel.parsing import parse_email
from src.core.storage import get_storage
from support_chat import service as chat_service
from tests.emails import build
from tests.fixtures.genai import ScriptedProvider

pytestmark = pytest.mark.db
BODY = "My tablet arrived with a cracked screen and the box was crushed in transit."
READY = json.dumps(
    {
        "reply": "Here is the summary:",
        "title": "Promotion code not applied",
        "missing": [],
        "ready_to_confirm": True,
        "requested_resolution": None,
    }
)


async def receive(raw: bytes) -> InboundEmail:
    async with async_session_factory()() as db:
        return await process_email(
            db, parse_email(raw), via="manual", own_address="care@volthaven.test",
            storage=get_storage(),
        )  # fmt: skip


async def test_email_hook_holds_the_reply(client: httpx.AsyncClient) -> None:
    from email_channel.notify import after_validation

    record = await receive(build(text=BODY))
    with sync_session() as db:
        complaint = db.get(Complaint, record.complaint_id)
        assert complaint is not None
        after_validation(db, complaint, "verified", "Dear Sara, a replacement.", auto_reply=False)
        db.commit()
        kinds = [o.kind for o in db.scalars(select(OutboundEmail).order_by(OutboundEmail.created_at))]
    assert kinds == ["acknowledgement", "holding"]


async def test_chat_hook_holds_the_reply(
    client: httpx.AsyncClient,
    create_user: Callable[..., User],
    make_token: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from support_chat import notify

    user = create_user(Role.CUSTOMER)
    headers = {"Authorization": f"Bearer {make_token(user.clerk_user_id)}"}
    monkeypatch.setattr(chat_service, "intake_provider", lambda: ScriptedProvider(READY))
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=headers)).json()
    base = f"/api/v1/chat/conversations/{conv['id']}"
    text = "The promotion code SAVE10 was not applied to my order at checkout."
    await client.post(f"{base}/messages", json={"text": text}, headers=headers)
    ref = (await client.post(f"{base}/confirm", headers=headers)).json()["complaint_ref"]
    with sync_session() as db:
        complaint = db.scalar(select(Complaint).where(Complaint.complaint_ref == ref))
        assert complaint is not None
        notify.after_validation(db, complaint, "verified", "We checked your order.", auto_reply=False)
        db.commit()
        kinds = list(db.scalars(select(ChatMessage.kind)))
    assert "reply" not in kinds and kinds.count("holding") == 1
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest -q tests/unit/test_auto_replies_setting.py tests/integration/test_auto_replies_setting.py`
Expected: FAIL — `ImportError: cannot import name 'AUTO_REPLIES_OFF'`, unexpected keyword `auto_reply`.

- [ ] **Step 4: Sender name**

`email_channel/tasks.py:136`:
```python
    message["From"] = formataddr(
        (app_settings.runtime().email.from_name, settings.mail_username or "")
    )
```
`email_channel/transport.py` `BrevoSender.send` — take the display name from the message:
```python
        name, _ = parseaddr(str(message["From"]))
        mailbox = {"name": name or s.mail_from_name, "email": s.mail_username}
```
(`import app_settings` in tasks.py; `from email.utils import getaddresses, parseaddr` in transport.py.)

- [ ] **Step 5: Review decision in `python_validation/pipeline.py`**

Add at module level:

```python
AUTO_REPLIES_OFF = "Automatic replies are off: approve the reply."


def review_reasons(verdict: str, reasons: list[str], *, auto_replies: bool) -> list[str] | None:
    """Why a person must look before the customer gets a reply; None if nobody must."""
    if verdict == Verdict.NEEDS_REVIEW:
        return reasons
    return None if auto_replies else [AUTO_REPLIES_OFF]
```

In `_apply`, replace `if verdict == Verdict.NEEDS_REVIEW:` … (the review branch) and the two
hook calls with:

```python
    review = review_reasons(
        verdict, reasons, auto_replies=app_settings.runtime().email.auto_replies
    )
    if review is not None:
        complaint.needs_review = True
        complaint.review_reason = "; ".join(review)[:2000]
        open_review_task(db, complaint, validation.id, review)
    else:
        ...  # the existing else-branch, unchanged
    ...
    held = review is not None and verdict != Verdict.NEEDS_REVIEW
    after_validation(db, complaint, verdict, draft, auto_reply=not held)
    email_after_validation(db, complaint, verdict, draft, auto_reply=not held)
```

(`import app_settings` at the top.)

- [ ] **Step 6: Notify hooks**

`email_channel/notify.py` `after_validation`:

```python
def after_validation(
    db: Session, complaint: Complaint, verdict: str, draft: str | None, *, auto_reply: bool = True
) -> None:
    ...  # unchanged up to the two branches
    if auto_reply and verdict in AUTO_REPLY_VERDICTS and draft:
        _queue(db, complaint, origin, "reply", draft + SIGNATURE)
    elif (verdict not in AUTO_REPLY_VERDICTS or not auto_reply) and "holding" not in kinds:
        body = compose("holding", name=origin.from_name, ref=complaint.complaint_ref)
        _queue(db, complaint, origin, "holding", body)
```

`support_chat/notify.py` `after_validation`: same signature change; the reply branch condition
becomes `if auto_reply and verdict in AUTO_REPLY_VERDICTS and draft:` and the holding branch
`elif (verdict not in AUTO_REPLY_VERDICTS or not auto_reply) and "holding" not in posted:`.

- [ ] **Step 7: Run tests**

Run: `uv run pytest -q tests/unit/test_auto_replies_setting.py tests/integration/test_auto_replies_setting.py && uv run pytest -q`
Expected: PASS, full suite green.

- [ ] **Step 8: Commit**

```bash
git add email_channel support_chat python_validation tests
git commit -m "feat(settings): sender name and automatic replies from Settings"
```

---

### Task 6: Scheduler tick and job gate

**Files:**
- Create: `app_settings/jobs.py`, `app_settings/tasks.py`
- Modify: `src/worker.py`, `tests/integration/test_mailbox_tasks.py` (`test_beat_runs_the_mailbox_check_and_outbox_flush`)
- Test: `tests/integration/test_scheduler_tick.py`

**Interfaces:**
- Consumes: `runtime()`, `JobRun`.
- Produces: `claim(job: str, interval_seconds: int, now: datetime | None = None) -> bool`; `tick(now: datetime | None = None, jobs: dict[str, Job] | None = None) -> list[str]`; Celery task `app_settings.tasks.tick`.

- [ ] **Step 1: Failing tests `tests/integration/test_scheduler_tick.py`**

```python
"""One Beat tick every 15 s; each job runs once per its configured interval."""

from datetime import UTC, datetime, timedelta

import pytest

from app_settings.jobs import Job, claim, tick

pytestmark = pytest.mark.db
T0 = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def test_claim_once_per_interval(clean_db: None) -> None:
    assert claim("mailbox-check", 60, T0)
    assert not claim("mailbox-check", 60, T0 + timedelta(seconds=30))
    assert claim("mailbox-check", 60, T0 + timedelta(seconds=60))


def test_tick_runs_only_due_jobs_and_survives_a_failure(clean_db: None) -> None:
    ran: list[str] = []

    def boom() -> None:
        raise RuntimeError("mail server down")

    jobs = {
        "a": Job(lambda s: 60, lambda: ran.append("a")),
        "broken": Job(lambda s: 60, boom),
        "b": Job(lambda s: 300, lambda: ran.append("b")),
    }
    assert tick(T0, jobs) == ["a", "b"]
    assert tick(T0 + timedelta(seconds=15), jobs) == []  # nothing due, broken not retried
    assert tick(T0 + timedelta(seconds=60), jobs) == ["a"]


def test_beat_schedules_only_the_tick() -> None:
    from src.worker import celery_app

    schedule = {v["task"]: v["schedule"] for v in celery_app.conf.beat_schedule.values()}
    assert schedule == {"app_settings.tasks.tick": 15.0}
    assert "app_settings.tasks" in celery_app.conf.include
```

Replace `test_beat_runs_the_mailbox_check_and_outbox_flush` in `tests/integration/test_mailbox_tasks.py` with:

```python
def test_mailbox_jobs_run_from_the_settings_tick() -> None:
    from app_settings.jobs import JOBS

    assert {"mailbox-check", "email-outbox", "sla-risk-scan"} <= set(JOBS)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest -q tests/integration/test_scheduler_tick.py`
Expected: FAIL — `No module named 'app_settings.jobs'`.

- [ ] **Step 3: `app_settings/jobs.py`**

```python
"""Periodic jobs on intervals set in Settings: Beat calls `tick` every 15 s."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.dialects.postgresql import insert

from app_settings.model import RuntimeSettings
from app_settings.store import runtime
from database.models import JobRun
from database.session import sync_session
from src.core.logging import get_logger

log = get_logger(__name__)
TICK_SECONDS = 15
GRACE_SECONDS = 5  # a job due a moment after a tick still runs on that tick


@dataclass(frozen=True)
class Job:
    interval: Callable[[RuntimeSettings], int]  # seconds, from the settings
    run: Callable[[], object]


def _mailbox() -> object:
    from email_channel.tasks import check

    return check()


def _outbox() -> object:
    from email_channel.tasks import flush

    return flush()


def _sla() -> object:
    from complaint_processing.tasks import scan_sla

    return scan_sla()


JOBS: dict[str, Job] = {
    "mailbox-check": Job(lambda s: s.email.mailbox_check_seconds, _mailbox),
    "email-outbox": Job(lambda s: s.email.outbox_flush_seconds, _outbox),
    "sla-risk-scan": Job(lambda s: s.operations.sla_scan_minutes * 60, _sla),
}


def claim(job: str, interval_seconds: int, now: datetime | None = None) -> bool:
    """True for exactly one caller per interval (a single atomic statement)."""
    now = now or datetime.now(UTC)
    due_before = now - timedelta(seconds=max(interval_seconds - GRACE_SECONDS, 1))
    stmt = (
        insert(JobRun)
        .values(job=job, last_run_at=now)
        .on_conflict_do_update(
            index_elements=[JobRun.job],
            set_={"last_run_at": now},
            where=JobRun.last_run_at <= due_before,
        )
        .returning(JobRun.job)
    )
    with sync_session() as db:
        claimed = db.execute(stmt).scalar_one_or_none() is not None
        db.commit()
    return claimed


def tick(now: datetime | None = None, jobs: dict[str, Job] | None = None) -> list[str]:
    """Run each due job; one failing job never stops the others. Returns the jobs that ran."""
    settings, ran = runtime(), []
    for name, job in (jobs or JOBS).items():
        try:
            if claim(name, job.interval(settings), now):
                job.run()  # the gate already advanced: a failure waits for the next interval
                ran.append(name)
        except Exception:
            log.exception("scheduler.job_failed", job=name)
    return ran
```

- [ ] **Step 4: `app_settings/tasks.py`**

```python
"""Celery entry point for the settings-driven scheduler (see app_settings.jobs)."""

from app_settings.jobs import tick as run_tick
from src.worker import celery_app


@celery_app.task(name="app_settings.tasks.tick")  # type: ignore[untyped-decorator]
def tick() -> list[str]:
    return run_tick()
```

- [ ] **Step 5: `src/worker.py`**

Add `"app_settings.tasks"` to `include`, add route `"app_settings.tasks.*": {"queue": "default"}`,
remove the `analytics_config` import, and replace `beat_schedule` with:

```python
    # One tick every 15 s; each job's own interval comes from the Settings page
    # (app_settings.jobs): mailbox check, e-mail outbox, SLA risk scan.
    beat_schedule={"settings-tick": {"task": "app_settings.tasks.tick", "schedule": 15.0}},
```

Update the module docstring of `email_channel/tasks.py` ("every minute … every 30 s") to
"on the intervals set in Settings (app_settings.jobs)".

- [ ] **Step 6: Run tests**

Run: `uv run pytest -q tests/integration/test_scheduler_tick.py tests/integration/test_mailbox_tasks.py && uv run pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app_settings src/worker.py email_channel/tasks.py tests
git commit -m "feat(settings): scheduler tick with per-job intervals from Settings"
```

---

### Task 7: Logos and public branding

**Files:**
- Create: `app_settings/logos.py`
- Modify: `src/api/routes/settings.py`, `src/api/schemas.py`, `src/api/routes/storefront.py` (`get_storefront_config`)
- Test: `tests/integration/test_branding_api.py`

**Interfaces:**
- Consumes: `save`, `load`, `current_row`, `logo_url`, `image_type` (from `storefront.images`).
- Produces: `POST /api/v1/settings/logo/{target}`, `DELETE /api/v1/settings/logo/{target}` (admin); public `GET /api/v1/branding` → `BrandingOut`, `GET /api/v1/branding/logo/{target}`; storefront `company` from settings.

- [ ] **Step 1: Failing tests**

```python
"""Logos (content-checked, public) and branding (public, from Settings)."""

from collections.abc import Callable

import httpx
import pytest

from database.models import Role

pytestmark = pytest.mark.db
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


async def test_admin_uploads_a_logo_that_everyone_can_load(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    up = await client.post("/api/v1/settings/logo/shop", headers=admin, files={"file": ("logo.png", PNG, "image/png")})
    assert up.status_code == 200, up.text
    branding = (await client.get("/api/v1/branding")).json()  # no sign-in
    assert branding["shop_logo_url"].startswith("/api/v1/branding/logo/shop?v=")
    image = await client.get("/api/v1/branding/logo/shop")
    assert image.status_code == 200 and image.content == PNG
    assert image.headers["x-content-type-options"] == "nosniff"
    assert (await client.delete("/api/v1/settings/logo/shop", headers=admin)).status_code == 204
    assert (await client.get("/api/v1/branding/logo/shop")).status_code == 404


@pytest.mark.parametrize(
    ("name", "data"),
    [("logo.svg", SVG), ("logo.png", SVG), ("big.png", PNG + b"\x00" * 1024 * 1024)],
    ids=["svg", "svg-renamed-png", "over-1mb"],
)
async def test_unsafe_or_large_logos_are_refused(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]], name: str, data: bytes
) -> None:
    response = await client.post("/api/v1/settings/logo/console", headers=auth_headers(Role.ADMIN), files={"file": (name, data, "image/png")})
    assert response.status_code == 422


async def test_only_admins_upload(client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]) -> None:
    response = await client.post("/api/v1/settings/logo/shop", headers=auth_headers(Role.AGENT), files={"file": ("l.png", PNG, "image/png")})
    assert response.status_code == 403


async def test_shop_details_follow_the_settings(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    current = (await client.get("/api/v1/settings", headers=admin)).json()
    s = current["settings"]
    branding = {k: v for k, v in s["branding"].items() if not k.endswith("_logo_key")}
    payload = {"version": current["version"], "email": s["email"], "ai": s["ai"], "operations": s["operations"],
               "branding": {**branding, "shop_name": "Nova Electronics", "phone": "+92 300 0000000"}}
    assert (await client.put("/api/v1/settings", headers=admin, json=payload)).status_code == 200
    company = (await client.get("/api/v1/storefront/config")).json()["company"]
    assert (company["name"], company["phone"]) == ("Nova Electronics", "+92 300 0000000")
    assert (await client.get("/api/v1/branding")).json()["shop_name"] == "Nova Electronics"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest -q tests/integration/test_branding_api.py`
Expected: FAIL — 404/405 on the logo endpoints.

- [ ] **Step 3: `app_settings/logos.py`**

```python
"""Shop and console logos: content-checked images in storage, key saved in Settings."""

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from app_settings.model import LogoTarget
from app_settings.store import current_row, load, save
from database.models import User
from src.core.storage import Storage
from storefront.images import EXTENSIONS, image_type

MAX_LOGO_BYTES = 1024 * 1024


class LogoError(ValueError):
    pass


def check(data: bytes) -> str:
    if not data:
        raise LogoError("The file is empty.")
    if len(data) > MAX_LOGO_BYTES:
        raise LogoError("Logos must be 1 MB or smaller.")
    media_type = image_type(data)  # from the content, never the name: SVG is refused
    if media_type is None:
        raise LogoError("Only PNG, JPEG and WebP logos are accepted.")
    return media_type


async def set_logo(
    db: AsyncSession, target: LogoTarget, data: bytes, storage: Storage, actor: User
) -> str:
    media_type = check(data)
    key = f"branding/{target}-{hashlib.sha256(data).hexdigest()[:12]}.{EXTENSIONS[media_type]}"
    storage.put(key, data, media_type)
    row = await current_row(db)
    settings = load(row.data if row else None)
    settings.branding = settings.branding.model_copy(update={f"{target}_logo_key": key})
    await save(db, settings, actor=actor, expected_version=None)
    return key


async def remove_logo(db: AsyncSession, target: LogoTarget, actor: User) -> None:
    row = await current_row(db)
    settings = load(row.data if row else None)
    settings.branding = settings.branding.model_copy(update={f"{target}_logo_key": None})
    await save(db, settings, actor=actor, expected_version=None)
```

- [ ] **Step 4: Endpoints (append to `src/api/routes/settings.py`)**

```python
class BrandingOut(BaseModel):  # put in src/api/schemas.py
    shop_name: str
    shop_tagline: str
    console_name: str
    support_email: str
    phone: str
    address: str
    hours: str
    shop_logo_url: str | None
    console_logo_url: str | None
```

```python
@router.post("/settings/logo/{target}", response_model=SettingsOut)
async def upload_logo(
    target: LogoTarget,
    file: UploadFile = File(...),
    actor: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> SettingsOut:
    try:
        await logos.set_logo(db, target, await file.read(), storage, actor)
    except logos.LogoError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return await _out(db)


@router.delete("/settings/logo/{target}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_logo(
    target: LogoTarget, actor: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> Response:
    await logos.remove_logo(db, target, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/branding", response_model=BrandingOut)
async def read_branding() -> BrandingOut:
    b = app_settings.runtime().branding
    return BrandingOut(
        **b.model_dump(exclude={"shop_logo_key", "console_logo_key"}),
        shop_logo_url=logo_url("shop", b.shop_logo_key),
        console_logo_url=logo_url("console", b.console_logo_key),
    )


@router.get("/branding/logo/{target}", response_class=Response, responses={200: {"content": {"image/*": {}}}})
async def branding_logo(target: LogoTarget, storage: Storage = Depends(get_storage)) -> Response:
    key = getattr(app_settings.runtime().branding, f"{target}_logo_key")
    if key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No logo")
    data = await run_in_threadpool(storage.get, key)
    return Response(
        content=data,
        media_type=image_type(data) or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"},
    )
```

Imports: `from fastapi import File, Response, UploadFile`, `from fastapi.concurrency import run_in_threadpool`,
`from app_settings import logos`, `from app_settings.model import LogoTarget`,
`from src.core.storage import Storage, get_storage`, `from storefront.images import image_type`,
`BrandingOut` from schemas. Make `/branding` routes public in `web/src/proxy.ts`? Not needed
(API host), but confirm the API has no global auth dependency: `grep -n "dependencies=" src/main.py`.

- [ ] **Step 5: Storefront company from settings (`src/api/routes/storefront.py`)**

```python
@router.get("/storefront/config", response_model=StorefrontConfig)
async def get_storefront_config() -> StorefrontConfig:
    """Company details (from Settings), delivery, returns and warranty facts, and the FAQ."""
    config = storefront_config()
    b = app_settings.runtime().branding
    company = config.company.model_copy(
        update={"name": b.shop_name, "tagline": b.shop_tagline, "address": b.address,
                "phone": b.phone, "support_email": b.support_email, "hours": b.hours}
    )  # fmt: skip
    return config.model_copy(update={"company": company})
```

- [ ] **Step 6: Run tests, OpenAPI, commit**

Run: `uv run pytest -q tests/integration/test_branding_api.py && uv run pytest -q`
Expected: PASS.
Run: `make openapi` (regenerates `web/openapi.json` and the web client).

```bash
git add app_settings src tests web/openapi.json web/src/lib/api/generated
git commit -m "feat(settings): logo upload and public branding"
```

---

### Task 8: Settings page (web)

**Files:**
- Create: `web/src/app/(app)/settings/general/page.tsx`, `web/src/components/settings/settings-manager.tsx`, `web/src/components/settings/logo-upload.tsx`
- Modify: `web/src/components/app-sidebar.tsx` (nav item)

**Interfaces:**
- Consumes (generated client): `readSettingsOptions`, `readSettingsQueryKey`, `updateSettingsMutation`, `uploadLogoMutation`, `deleteLogoMutation`; types `SettingsOut`, `SettingsUpdate`. (Check exact names in `web/src/lib/api/generated/@tanstack/react-query.gen.ts` after Task 7.)

- [ ] **Step 1: Page `web/src/app/(app)/settings/general/page.tsx`**

```tsx
import { redirect } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { SettingsManager } from "@/components/settings/settings-manager";
import { getCurrentUser } from "@/lib/api/server";

export const metadata = { title: "Settings" };

export default async function SettingsPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok" || result.user.role !== "admin") redirect("/dashboard");
  return (
    <>
      <PageHeader
        title="Settings"
        description="E-mail timing, AI behaviour, review thresholds and branding. Changes apply within about 15 seconds, with no redeploy. Keys and passwords stay on the server."
      />
      <SettingsManager />
    </>
  );
}
```

- [ ] **Step 2: `logo-upload.tsx`**

```tsx
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ImagePlus, Trash2 } from "lucide-react";
import { useRef } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  deleteLogoMutation,
  readSettingsQueryKey,
  uploadLogoMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { API_URL } from "@/lib/api/runtime-config";

export function LogoUpload({
  target,
  label,
  url,
}: {
  target: "shop" | "console";
  label: string;
  url: string | null | undefined;
}) {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const done = (message: string) => ({
    onSuccess: () => {
      toast.success(message);
      queryClient.invalidateQueries({ queryKey: readSettingsQueryKey() });
      queryClient.invalidateQueries({ queryKey: [{ _id: "readBranding" }] });
    },
    onError: (err: unknown) => toast.error(apiErrorMessage(err, "Logo update failed.")),
  });
  const upload = useMutation({ ...uploadLogoMutation(), ...done("Logo updated") });
  const remove = useMutation({ ...deleteLogoMutation(), ...done("Logo removed") });

  return (
    <div className="flex items-center gap-4 rounded-xl border p-4">
      <div className="grid size-16 shrink-0 place-items-center overflow-hidden rounded-lg border bg-muted">
        {url ? (
          // eslint-disable-next-line @next/next/no-img-element -- served by the API host
          <img src={`${API_URL}${url}`} alt={`${label} logo`} className="size-full object-contain" />
        ) : (
          <span className="text-xs text-muted-foreground">None</span>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-medium">{label} logo</p>
        <p className="text-xs text-muted-foreground">PNG, JPEG or WebP, up to 1 MB. Square works best.</p>
      </div>
      <input
        ref={input}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) upload.mutate({ path: { target }, body: { file } });
          e.target.value = "";
        }}
      />
      <Button variant="outline" size="sm" disabled={upload.isPending} onClick={() => input.current?.click()}>
        <ImagePlus /> Upload
      </Button>
      {url ? (
        <Button variant="ghost" size="sm" disabled={remove.isPending} onClick={() => remove.mutate({ path: { target } })}>
          <Trash2 /> Remove
        </Button>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 3: `settings-manager.tsx`**

```tsx
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { LogoUpload } from "@/components/settings/logo-upload";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  readSettingsOptions,
  readSettingsQueryKey,
  updateSettingsMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { SettingsOut, SettingsUpdate } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";

type Form = Omit<SettingsUpdate, "version">;
const EFFORTS = ["none", "minimal", "low", "medium", "high", "xhigh", "max"] as const;

function toForm(s: SettingsOut): Form {
  const { shop_logo_key: _s, console_logo_key: _c, ...branding } = s.settings.branding;
  return { email: s.settings.email, ai: s.settings.ai, operations: s.settings.operations, branding };
}

function Field({ label, help, children }: { label: string; help?: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5 sm:grid-cols-[16rem_1fr] sm:items-start sm:gap-6">
      <div>
        <Label>{label}</Label>
        {help ? <p className="mt-1 text-xs text-muted-foreground">{help}</p> : null}
      </div>
      <div className="max-w-md">{children}</div>
    </div>
  );
}

function NumberInput({ value, min, max, onChange }: { value: number; min: number; max: number; onChange: (v: number) => void }) {
  return <Input type="number" min={min} max={max} value={value} onChange={(e) => onChange(Number(e.target.value))} />;
}

export function SettingsManager() {
  const queryClient = useQueryClient();
  const settings = useQuery(readSettingsOptions());
  const [form, setForm] = useState<Form | null>(null);
  useEffect(() => {
    if (settings.data) setForm(toForm(settings.data));
  }, [settings.data]);
  const save = useMutation({
    ...updateSettingsMutation(),
    onSuccess: (data) => {
      toast.success("Settings saved. They apply within about 15 seconds.");
      queryClient.setQueryData(readSettingsQueryKey(), data);
    },
    onError: (err) => toast.error(apiErrorMessage(err, "Settings were not saved.")),
  });

  if (settings.isPending || !form) return <Skeleton className="h-96 w-full" />;
  if (settings.isError) return <p className="text-sm text-destructive">{apiErrorMessage(settings.error)}</p>;
  const data = settings.data;
  const dirty = JSON.stringify(form) !== JSON.stringify(toForm(data));
  const set = <G extends keyof Form>(group: G, patch: Partial<Form[G]>) =>
    setForm((f) => (f ? { ...f, [group]: { ...f[group], ...patch } } : f));
  const models = data.suggested_models[form.ai.provider] ?? [];

  const footer = (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
      <p className="text-xs text-muted-foreground">
        {data.updated_at
          ? `Last changed by ${data.updated_by ?? "an administrator"} on ${new Date(data.updated_at).toLocaleString()}`
          : "Using the default settings."}
      </p>
      <div className="flex gap-2">
        <Button variant="ghost" disabled={!dirty} onClick={() => setForm(toForm(data))}>Discard</Button>
        <Button disabled={!dirty || save.isPending} onClick={() => save.mutate({ body: { version: data.version, ...form } })}>
          Save changes
        </Button>
      </div>
    </div>
  );

  return (
    <Tabs defaultValue="email" className="space-y-6">
      <TabsList className="flex-wrap">
        <TabsTrigger value="email">E-mail & timing</TabsTrigger>
        <TabsTrigger value="ai">AI</TabsTrigger>
        <TabsTrigger value="operations">Operations</TabsTrigger>
        <TabsTrigger value="branding">Branding</TabsTrigger>
        <TabsTrigger value="policy">Policy facts</TabsTrigger>
      </TabsList>

      <TabsContent value="email" className="space-y-6 rounded-xl border p-6">
        <Field label="Check the mailbox every (seconds)" help="60 to 3600. New e-mails become complaints on this schedule.">
          <NumberInput value={form.email.mailbox_check_seconds} min={60} max={3600} onChange={(v) => set("email", { mailbox_check_seconds: v })} />
        </Field>
        <Field label="Send queued e-mails every (seconds)" help="15 to 600.">
          <NumberInput value={form.email.outbox_flush_seconds} min={15} max={600} onChange={(v) => set("email", { outbox_flush_seconds: v })} />
        </Field>
        <Field label="Sender name" help="Shown as the From name on every e-mail.">
          <Input value={form.email.from_name} maxLength={80} onChange={(e) => set("email", { from_name: e.target.value })} />
        </Field>
        <Field label="Send automatic replies" help="Off: verified replies also wait for a reviewer to approve them (e-mail and chat).">
          <Switch checked={form.email.auto_replies} onCheckedChange={(v) => set("email", { auto_replies: v })} />
        </Field>
        {footer}
      </TabsContent>

      <TabsContent value="ai" className="space-y-6 rounded-xl border p-6">
        <Field label="Provider" help="Only providers with an API key on the server can be chosen.">
          <Select value={form.ai.provider} onValueChange={(v) => set("ai", { provider: v as Form["ai"]["provider"], model: data.suggested_models[v]?.[0] ?? "" })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {(["openai", "anthropic"] as const).map((p) => (
                <SelectItem key={p} value={p} disabled={!data.providers_available.includes(p)}>
                  {p === "openai" ? "OpenAI" : "Anthropic"}{data.providers_available.includes(p) ? "" : " (no API key)"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="Model" help="Pick a suggestion or type another model name for this provider.">
          <Input list="model-suggestions" value={form.ai.model} maxLength={100} onChange={(e) => set("ai", { model: e.target.value })} />
          <datalist id="model-suggestions">{models.map((m) => <option key={m} value={m} />)}</datalist>
        </Field>
        <Field label="Reasoning effort" help="Lower is faster and cheaper; higher can be more careful.">
          <Select value={form.ai.effort} onValueChange={(v) => set("ai", { effort: v as Form["ai"]["effort"] })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>{EFFORTS.map((e) => <SelectItem key={e} value={e}>{e}</SelectItem>)}</SelectContent>
          </Select>
        </Field>
        <Field label="Policy passages to read" help="3 to 20 passages retrieved from the knowledge base per complaint.">
          <NumberInput value={form.ai.retrieval_limit} min={3} max={20} onChange={(v) => set("ai", { retrieval_limit: v })} />
        </Field>
        <Field label="Analyse new complaints automatically" help="Off: staff start the analysis with Re-run analysis.">
          <Switch checked={form.ai.auto_analysis} onCheckedChange={(v) => set("ai", { auto_analysis: v })} />
        </Field>
        {footer}
      </TabsContent>

      <TabsContent value="operations" className="space-y-6 rounded-xl border p-6">
        <Field label="SLA risk scan every (minutes)" help="1 to 60.">
          <NumberInput value={form.operations.sla_scan_minutes} min={1} max={60} onChange={(v) => set("operations", { sla_scan_minutes: v })} />
        </Field>
        <Field label="Minimum score for 'verified'" help="50 to 100. Below it, a complaint goes to manual review.">
          <NumberInput value={form.operations.verified_min_score} min={50} max={100} onChange={(v) => set("operations", { verified_min_score: v })} />
        </Field>
        <Field label="Always review from escalation level" help="1 to 5. Complaints at or above it always get a human review.">
          <NumberInput value={form.operations.always_review_escalation_level} min={1} max={5} onChange={(v) => set("operations", { always_review_escalation_level: v })} />
        </Field>
        {footer}
      </TabsContent>

      <TabsContent value="branding" className="space-y-6 rounded-xl border p-6">
        <div className="grid gap-3 lg:grid-cols-2">
          <LogoUpload target="shop" label="Shop" url={data.shop_logo_url} />
          <LogoUpload target="console" label="Console" url={data.console_logo_url} />
        </div>
        <Field label="Shop name"><Input value={form.branding.shop_name} maxLength={60} onChange={(e) => set("branding", { shop_name: e.target.value })} /></Field>
        <Field label="Shop tagline"><Input value={form.branding.shop_tagline} maxLength={140} onChange={(e) => set("branding", { shop_tagline: e.target.value })} /></Field>
        <Field label="Console name"><Input value={form.branding.console_name} maxLength={40} onChange={(e) => set("branding", { console_name: e.target.value })} /></Field>
        <Field label="Support e-mail"><Input type="email" value={form.branding.support_email} maxLength={120} onChange={(e) => set("branding", { support_email: e.target.value })} /></Field>
        <Field label="Phone"><Input value={form.branding.phone} maxLength={40} onChange={(e) => set("branding", { phone: e.target.value })} /></Field>
        <Field label="Address"><Input value={form.branding.address} maxLength={200} onChange={(e) => set("branding", { address: e.target.value })} /></Field>
        <Field label="Opening hours"><Input value={form.branding.hours} maxLength={100} onChange={(e) => set("branding", { hours: e.target.value })} /></Field>
        {footer}
      </TabsContent>

      <TabsContent value="policy" className="space-y-4 rounded-xl border p-6">
        <p className="text-sm text-muted-foreground">
          These come from the policy documents, so the shop, the AI and the rules always agree. To change one, upload a new version of the document in the Knowledge base.
        </p>
        <Table>
          <TableHeader><TableRow><TableHead>Fact</TableHead><TableHead>Value</TableHead><TableHead>Source</TableHead></TableRow></TableHeader>
          <TableBody>
            {data.policy_facts.map((f) => (
              <TableRow key={f.fact}>
                <TableCell>{f.fact}</TableCell>
                <TableCell className="font-medium">{f.value}</TableCell>
                <TableCell className="font-mono text-xs">{f.source}{f.version ? ` v${f.version}` : " (not active)"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TabsContent>
    </Tabs>
  );
}
```

Check `Switch` and `Tabs` exist in `web/src/components/ui` (they do: `switch.tsx`, `tabs.tsx`).
Adjust generated names/types if Task 7's client differs (e.g. `readSettingsOptions`).

- [ ] **Step 4: Sidebar item**

In `web/src/components/app-sidebar.tsx` Administration group, after "Users & roles":
```tsx
      { title: "Settings", href: "/settings/general", icon: Settings2, roles: ["admin"] },
```
(add `Settings2` to the lucide import.)

- [ ] **Step 5: Verify**

Run: `pnpm --dir web exec prettier --write src && pnpm --dir web lint && pnpm --dir web typecheck && pnpm --dir web build`
Expected: clean; `/settings/general` in the build output.

- [ ] **Step 6: Commit**

```bash
git add web/src
git commit -m "feat(web): Settings page with e-mail, AI, operations, branding and policy tabs"
```

---

### Task 9: Branding in the shop, console and browser tab

**Files:**
- Create: `web/src/lib/branding.tsx`
- Modify: `web/src/components/shop/site-header.tsx` (`Logo`), `web/src/components/app-sidebar.tsx` (header), `web/src/app/(shop)/layout.tsx` (icon + title)

**Interfaces:**
- Consumes: `readBrandingOptions` (generated), `API_URL`.
- Produces: `useBranding()`, `<BrandMark target="shop" | "console" />`.

- [ ] **Step 1: `web/src/lib/branding.tsx`**

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";

import { readBrandingOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import { API_URL } from "@/lib/api/runtime-config";
import { cn } from "@/lib/utils";

export function useBranding() {
  return useQuery({ ...readBrandingOptions(), staleTime: 60_000 });
}

/** The uploaded logo, or the initials badge when there is none. */
export function BrandMark({ target, className }: { target: "shop" | "console"; className?: string }) {
  const { data } = useBranding();
  const name = (target === "shop" ? data?.shop_name : data?.console_name) ?? (target === "shop" ? "VoltHaven" : "SupportNova");
  const url = target === "shop" ? data?.shop_logo_url : data?.console_logo_url;
  if (url) {
    // eslint-disable-next-line @next/next/no-img-element -- served by the API host
    return <img src={`${API_URL}${url}`} alt={`${name} logo`} className={cn("size-8 rounded-lg object-contain", className)} />;
  }
  const initials = name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  return (
    <span className={cn("flex size-8 items-center justify-center rounded-lg text-xs font-bold", target === "shop" ? "bg-brand text-brand-foreground shadow-sm shadow-brand/30" : "bg-primary text-primary-foreground", className)}>
      {initials}
    </span>
  );
}
```

- [ ] **Step 2: Use it**

- `site-header.tsx` `Logo`: replace the `VH` span with `<BrandMark target="shop" />` and the
  name span with `{useBranding().data?.shop_name?.split(" ")[0] ?? "VoltHaven"}` (first word, as
  today's "VoltHaven"; make `Logo` a client component or call the hook in it — the file is
  already `"use client"`, check line 1).
- `app-sidebar.tsx` header: replace the `SN` span with `<BrandMark target="console" className="size-7" />`
  and `SupportNova` with `{useBranding().data?.console_name ?? "SupportNova"}`.
- `(shop)/layout.tsx`: replace the static `metadata` with

```tsx
import type { Metadata } from "next";

const SERVER_API_URL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function generateMetadata(): Promise<Metadata> {
  try {
    const res = await fetch(`${SERVER_API_URL}/api/v1/branding`, { next: { revalidate: 60 } });
    const b = (await res.json()) as { shop_name: string; shop_logo_url: string | null };
    return {
      title: { absolute: b.shop_name, template: `%s · ${b.shop_name.split(" ")[0]}` },
      icons: b.shop_logo_url ? { icon: `${SERVER_API_URL}${b.shop_logo_url}` } : undefined,
    };
  } catch {
    return { title: { absolute: "VoltHaven Electronics", template: "%s · VoltHaven" } };
  }
}
```

- [ ] **Step 3: Verify in the browser**

Run `pnpm --dir web build`, then with the local API running: upload a PNG logo as admin on
`/settings/general`, reload `/` — header shows the logo, the tab icon changes; remove it — the
badge returns. Rename the shop — header, footer and tab title follow within a minute.

- [ ] **Step 4: Commit**

```bash
git add web/src
git commit -m "feat(web): shop and console branding from Settings"
```

---

### Task 10: Documentation and final verification

**Files:**
- Modify: `README.md`, `documentation/deployment.md`, `documentation/user_guide.md`, `documentation/project_report.md`, `AI_USAGE.md`, test counts wherever stated.

- [ ] **Step 1: Docs**

- `documentation/user_guide.md`: a "Settings (administrators)" section listing the tabs, the limits, "applies within ~15 seconds", logo rules, and that policy numbers change by uploading a policy version.
- `documentation/deployment.md`: Beat now schedules one `app_settings.tasks.tick` every 15 s (start command unchanged); intervals are set in Settings; the migration runs in the pre-deploy step.
- `README.md` / `project_report.md`: mention Settings under features; update test counts (`uv run pytest -q | tail -1`).
- `AI_USAGE.md`: new entry (date 2026-09-28, files, changes, tests, "Verified by: to be completed by the team").

- [ ] **Step 2: Full verification**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -q`
Run: `pnpm --dir web lint && pnpm --dir web typecheck && pnpm --dir web build`
Expected: all clean.

- [ ] **Step 3: Commit**

```bash
git add README.md documentation AI_USAGE.md
git commit -m "docs: admin settings and branding"
```
