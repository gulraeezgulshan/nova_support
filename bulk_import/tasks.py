"""Run a previewed bulk upload in the background."""

import asyncio

from bulk_import.service import mark_failed, run
from database.session import task_session
from src.worker import celery_app


async def _run(batch_id: str) -> None:
    try:
        async with task_session() as db:
            await run(db, batch_id)
    except Exception:
        async with task_session() as db:
            await mark_failed(db, batch_id)
        raise


@celery_app.task(name="bulk_import.tasks.run_import")  # type: ignore[untyped-decorator]
def run_import(batch_id: str) -> None:
    asyncio.run(_run(batch_id))
