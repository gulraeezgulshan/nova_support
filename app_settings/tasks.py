"""Celery entry point for the settings-driven scheduler (see app_settings.jobs)."""

from app_settings.jobs import tick as run_tick
from src.worker import celery_app


@celery_app.task(name="app_settings.tasks.tick")  # type: ignore[untyped-decorator]
def tick() -> list[str]:
    return run_tick()
