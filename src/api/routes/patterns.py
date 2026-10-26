"""Settings → Patterns (admin only): risk-signal words, classifier phrases, promise wording.

Drafts are tested in a separate, time-limited process (`pattern_lab`), so a slow regex is
refused instead of hanging the API, and a draft never reaches the run-time settings.
"""

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app_settings
from app_settings import StaleSettingsError
from app_settings.patterns import signal_descriptions, supported_by
from database.models import AuditEvent, Category, Role, Subcategory, User
from database.session import get_db
from pattern_lab.lab import dataset_check, stress_check, try_text
from pattern_lab.models import DatasetCheckOut, TextTestOut
from pattern_lab.sandbox import LabError, TooSlowError, run_limited
from security.dependencies import require_roles
from src.api.schemas import (
    DatasetCheckIn,
    PatternsOut,
    PatternsUpdate,
    PatternTestIn,
    RecomputeOut,
    RecomputeQueuedOut,
)

router = APIRouter(tags=["patterns"])
admin_only = require_roles(Role.ADMIN)
URL = "/settings/patterns"
SAVE_SECONDS = TEXT_SECONDS = 2.0
DATASET_SECONDS = 30.0
TOO_LONG = "Testing took too long: a pattern may be very slow."


def enqueue_recompute(actor_id: str | None) -> None:
    from app_settings.tasks import recompute_signals

    recompute_signals.delay(actor_id)


async def _taxonomy(db: AsyncSession, *, active_only: bool) -> dict[str, list[str]]:
    query = select(Category.code, Subcategory.code).outerjoin(
        Subcategory, Subcategory.category_id == Category.id
    )
    if active_only:
        query = query.where(Category.is_active, Subcategory.is_active)
    taxonomy: dict[str, list[str]] = {}
    for category, subcategory in (await db.execute(query)).all():
        taxonomy.setdefault(category, [])
        if subcategory:
            taxonomy[category].append(subcategory)
    return taxonomy


async def _out(db: AsyncSession) -> PatternsOut:
    row = await app_settings.current_row(db)
    who = await db.get(User, row.updated_by_id) if row and row.updated_by_id else None
    last = await db.scalar(
        select(AuditEvent)
        .where(AuditEvent.action == "patterns.signals_recomputed")
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(1)
    )
    return PatternsOut(
        patterns=app_settings.load(row.data if row else None).patterns,
        defaults=app_settings.defaults().patterns,
        version=row.version if row else 0,
        updated_at=row.updated_at if row else None,
        updated_by=(who.full_name or who.email) if who else None,
        signal_descriptions=signal_descriptions(),
        supported_by=supported_by(),
        last_recompute=RecomputeOut(at=last.occurred_at, **(last.after or {})) if last else None,
    )


async def _limited(target: Any, args: tuple[Any, ...], seconds: float) -> Any:
    try:
        return await asyncio.to_thread(run_limited, target, args, seconds)
    except TooSlowError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, TOO_LONG) from exc
    except LabError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.get(URL, response_model=PatternsOut)
async def read_patterns(
    _: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> PatternsOut:
    return await _out(db)


@router.put(URL, response_model=PatternsOut)
async def update_patterns(
    payload: PatternsUpdate, actor: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> PatternsOut:
    taxonomy = await _taxonomy(db, active_only=False)
    for category, subs in payload.patterns.classifier.items():
        for subcategory in subs:
            if subcategory not in taxonomy.get(category, []):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    f"Classifier {category}/{subcategory}: subcategory does not exist.",
                )
    try:
        draft = payload.patterns.model_dump()
        await asyncio.to_thread(run_limited, stress_check, (draft,), SAVE_SECONDS)
    except TooSlowError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Patterns are too slow: {exc.where or 'a pattern'}",
        ) from exc
    row = await app_settings.current_row(db)
    stored = app_settings.load(row.data if row else None)
    try:
        await app_settings.save(
            db,
            stored.model_copy(update={"patterns": payload.patterns}),
            actor=actor,
            expected_version=payload.version,
            action="settings.updated",
            audit_group="patterns",
        )
    except StaleSettingsError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Someone else changed the settings; reload and try again."
        ) from exc
    return await _out(db)


@router.post(f"{URL}/test", response_model=TextTestOut)
async def test_patterns(
    payload: PatternTestIn, _: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    args = (
        app_settings.runtime(fresh=True).model_dump(),
        payload.draft.model_dump(),
        payload.text,
        await _taxonomy(db, active_only=True),
    )
    result: dict[str, Any] = await _limited(try_text, args, TEXT_SECONDS)
    return result


@router.post(f"{URL}/dataset-check", response_model=DatasetCheckOut)
async def check_patterns_on_dataset(
    payload: DatasetCheckIn, _: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    args = (
        app_settings.runtime(fresh=True).model_dump(),
        payload.draft.model_dump(),
        await _taxonomy(db, active_only=True),
    )
    result: dict[str, Any] = await _limited(dataset_check, args, DATASET_SECONDS)
    return result


@router.post(
    f"{URL}/recompute-signals",
    response_model=RecomputeQueuedOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def recompute_signals(actor: User = Depends(admin_only)) -> RecomputeQueuedOut:
    enqueue_recompute(str(actor.id))
    return RecomputeQueuedOut(queued=True)
