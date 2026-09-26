import uuid

from database.session import sync_session
from knowledge_base.embeddings import get_embedder
from knowledge_base.ingestion import ingest_version
from src.core.config import get_settings
from src.core.storage import get_storage
from src.worker import celery_app


@celery_app.task(name="knowledge_base.tasks.ingest_document_version")  # type: ignore[untyped-decorator]
def ingest_document_version(version_id: str) -> None:
    with sync_session() as db:
        ingest_version(
            db,
            uuid.UUID(version_id),
            storage=get_storage(),
            embedder=get_embedder(),
            settings=get_settings(),
        )
