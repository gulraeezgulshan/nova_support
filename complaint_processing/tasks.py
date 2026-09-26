"""Background processing of a complaint: GenAI analysis (Pipeline 1), then ground-truth
validation (Pipeline 2). The two pipelines are independent modules; this task only runs
them in order."""

import uuid

from database.session import sync_session
from genai_pipeline.pipeline import run_analysis
from genai_pipeline.providers import ProviderUnavailableError, get_provider
from knowledge_base.embeddings import get_embedder
from python_validation.pipeline import run_validation
from src.core.config import get_settings
from src.worker import celery_app

# Transient provider outages are retried with growing delays; meanwhile the rule matrix is
# applied on its own, so a critical complaint is escalated even while the GenAI is down.
MAX_TASK_RETRIES = 2


def process(complaint_id: uuid.UUID, triggered_by: uuid.UUID | None = None) -> str:
    with sync_session() as db:
        run_analysis(
            db,
            complaint_id,
            provider=get_provider(),
            embedder=get_embedder(),
            settings=get_settings(),
            triggered_by=triggered_by,
        )
    with sync_session() as db:
        return str(run_validation(db, complaint_id, triggered_by).verdict)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="complaint_processing.tasks.process_complaint",
    bind=True,
    max_retries=MAX_TASK_RETRIES,
)
def process_complaint(self, complaint_id: str, triggered_by: str | None = None) -> str:  # type: ignore[no-untyped-def]
    cid = uuid.UUID(complaint_id)
    actor = uuid.UUID(triggered_by) if triggered_by else None
    try:
        return process(cid, actor)
    except ProviderUnavailableError as exc:
        with sync_session() as db:
            run_validation(db, cid, actor)
        raise self.retry(exc=exc, countdown=15 * (self.request.retries + 1)) from exc
