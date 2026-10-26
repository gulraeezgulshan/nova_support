"""Celery entry point for the settings-driven scheduler (see app_settings.jobs)."""

import uuid

from app_settings.jobs import tick as run_tick
from src.worker import celery_app


@celery_app.task(name="app_settings.tasks.tick")  # type: ignore[untyped-decorator]
def tick() -> list[str]:
    return run_tick()


@celery_app.task(name="app_settings.tasks.recompute_signals")  # type: ignore[untyped-decorator]
def recompute_signals(actor_id: str | None = None) -> dict[str, int]:
    """Re-detect every stored complaint's risk signals with the saved patterns."""
    import app_settings
    from complaint_processing.recompute_signals import recompute
    from database import audit
    from database.session import sync_session

    app_settings.runtime(fresh=True)  # the patterns saved a moment ago
    changed, total = recompute()
    result = {"changed": changed, "total": total}
    with sync_session() as db:
        audit.record_sync(
            db,
            "patterns.signals_recomputed",
            "settings",
            "patterns",
            actor_user_id=uuid.UUID(actor_id) if actor_id else None,
            after=result,
        )
    return result
