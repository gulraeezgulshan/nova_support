import uuid

from database.session import sync_session
from genai_pipeline.pipeline import run_analysis
from genai_pipeline.providers import ProviderUnavailableError, get_provider
from knowledge_base.embeddings import get_embedder
from src.core.config import get_settings
from src.worker import celery_app

# Transient provider outages are retried with growing delays, then the complaint stays
# flagged for manual review (set by the pipeline) instead of retrying forever.
MAX_TASK_RETRIES = 2


@celery_app.task(  # type: ignore[untyped-decorator]
    name="genai_pipeline.tasks.analyze_complaint",
    bind=True,
    max_retries=MAX_TASK_RETRIES,
)
def analyze_complaint(self, complaint_id: str, triggered_by: str | None = None) -> str:  # type: ignore[no-untyped-def]
    try:
        with sync_session() as db:
            run = run_analysis(
                db,
                uuid.UUID(complaint_id),
                provider=get_provider(),
                embedder=get_embedder(),
                settings=get_settings(),
                triggered_by=uuid.UUID(triggered_by) if triggered_by else None,
            )
            return str(run.status)
    except ProviderUnavailableError as exc:
        raise self.retry(exc=exc, countdown=15 * (self.request.retries + 1)) from exc
