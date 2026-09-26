"""Background ingestion of one document version: parse -> chunk -> embed -> store."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database.audit import record_sync
from database.models import Chunk, DocumentVersion, IngestStatus
from document_processing.chunking import chunk_sections
from document_processing.parsers import parse_document
from document_processing.validation import FILE_TYPE_BY_MEDIA_TYPE
from knowledge_base.embeddings import Embedder
from knowledge_base.impact import flag_affected_complaints, superseded_by
from knowledge_base.versioning import VersionTransitionError, plan_activation, to_state
from src.core.config import Settings
from src.core.logging import get_logger
from src.core.storage import Storage

log = get_logger(__name__)


class IngestError(Exception):
    pass


def chunk_code(doc_code: str, version: str, ordinal: int) -> str:
    return f"{doc_code}@{version}#{ordinal:03d}"


def ingest_version(
    db: Session,
    version_id: uuid.UUID,
    *,
    storage: Storage,
    embedder: Embedder,
    settings: Settings,
) -> DocumentVersion:
    version = db.get(DocumentVersion, version_id)
    if version is None:
        raise IngestError(f"Document version {version_id} not found")

    version.ingest_status = IngestStatus.PROCESSING
    version.ingest_error = None
    db.commit()

    try:
        parsed = parse_document(
            storage.get(version.storage_key), FILE_TYPE_BY_MEDIA_TYPE[version.media_type]
        )
        drafts = chunk_sections(
            parsed.sections, settings.chunk_max_tokens, settings.chunk_overlap_tokens
        )
        if not drafts:
            raise IngestError("No extractable text found (scanned image PDFs need OCR).")
        vectors = embedder.embed_documents([d.embedding_text for d in drafts])

        doc_code = version.document.doc_code
        db.execute(delete(Chunk).where(Chunk.document_version_id == version.id))  # idempotent
        db.add_all(
            Chunk(
                chunk_code=chunk_code(doc_code, version.version, d.ordinal),
                document_version_id=version.id,
                doc_code=doc_code,
                version=version.version,
                ordinal=d.ordinal,
                section=d.section,
                heading=d.heading,
                page_start=d.page_start,
                page_end=d.page_end,
                content=d.content,
                token_count=d.token_count,
                embedding=vector,
            )
            for d, vector in zip(drafts, vectors, strict=True)
        )
        version.page_count = parsed.page_count
        version.chunk_count = len(drafts)
        version.ingest_status = IngestStatus.READY
        version.processed_at = datetime.now(UTC)
        record_sync(
            db,
            "document_version.ingested",
            "document_version",
            version.id,
            after={"chunks": len(drafts), "pages": parsed.page_count},
        )
        if version.activate_on_ready:
            try:
                apply_activation_sync(db, version)
            except VersionTransitionError as exc:  # stays a ready draft; admin can decide
                record_sync(
                    db,
                    "document_version.activation_skipped",
                    "document_version",
                    version.id,
                    after={"reason": str(exc)},
                )
        db.commit()
        log.info("ingest.completed", version_id=str(version.id), chunks=len(drafts))
    except Exception as exc:
        db.rollback()
        version = db.get(DocumentVersion, version_id)
        assert version is not None
        version.ingest_status = IngestStatus.FAILED
        version.ingest_error = str(exc)[:2000]
        record_sync(
            db,
            "document_version.ingest_failed",
            "document_version",
            version.id,
            after={"error": version.ingest_error},
        )
        db.commit()
        log.warning("ingest.failed", version_id=str(version_id), error=str(exc))
    return version


def apply_activation_sync(
    db: Session, version: DocumentVersion, actor_user_id: uuid.UUID | None = None
) -> None:
    siblings = db.scalars(
        select(DocumentVersion).where(DocumentVersion.document_id == version.document_id)
    ).all()
    changes = plan_activation([to_state(v) for v in siblings], version.id, date.today())
    by_id = {v.id: v for v in siblings}
    # Supersede first and flush, so the "one active version" index is never violated.
    for vid, status in changes.items():
        if vid != version.id:
            by_id[vid].status = status
    db.flush()
    if version.id in changes:
        version.status = changes[version.id]
    record_sync(
        db,
        "document_version.activated",
        "document_version",
        version.id,
        actor_user_id=actor_user_id,
        after={str(k): v for k, v in changes.items()},
    )
    if changes.get(version.id) == "active":
        flag_affected_complaints(
            db,
            version.document_id,
            superseded_by(changes, list(siblings)),
            version.version,
            actor_user_id,
        )
