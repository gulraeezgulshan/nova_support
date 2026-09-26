"""Knowledge-base use cases called by the API: upload, activate, retire, reprocess."""

import uuid
from datetime import date

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import audit
from database.models import Document, DocumentVersion, IngestStatus, User, VersionStatus
from document_processing.parsers import ParseError, parse_document
from document_processing.validation import (
    MEDIA_TYPES,
    DocumentValidationError,
    build_metadata,
    detect_file_type,
    extract_header_metadata,
    sha256_hex,
)
from knowledge_base.config import get_kb_config
from knowledge_base.impact import flag_affected_complaints, superseded_by
from knowledge_base.versioning import plan_activation, plan_retirement, to_state
from src.core.config import Settings
from src.core.logging import get_logger
from src.core.storage import Storage, safe_filename

log = get_logger(__name__)


class DuplicateDocumentError(Exception):
    pass


def enqueue_ingest(version_id: uuid.UUID) -> None:
    """Hand the version to a Celery worker. Tests replace this function."""
    from knowledge_base.tasks import ingest_document_version

    ingest_document_version.delay(str(version_id))


def _safe_enqueue(version_id: uuid.UUID) -> None:
    try:
        enqueue_ingest(version_id)
    except Exception as exc:  # broker down: version stays "pending"; admin can reprocess
        log.error("ingest.enqueue_failed", version_id=str(version_id), error=str(exc))


async def upload_document(
    db: AsyncSession,
    *,
    filename: str,
    data: bytes,
    form: dict[str, str | None],
    activate: bool,
    actor: User | None,
    storage: Storage,
    settings: Settings,
    enqueue: bool = True,
) -> DocumentVersion:
    """Validate, store and register a new document version. `actor=None` = system import."""
    file_type = detect_file_type(filename, data, settings.max_upload_bytes)
    digest = sha256_hex(data)
    existing = await db.scalar(select(DocumentVersion).where(DocumentVersion.sha256 == digest))
    if existing is not None:
        raise DuplicateDocumentError(
            "This exact file was already uploaded "
            f"(version {existing.version} of document {existing.document_id})."
        )

    try:
        parsed = await run_in_threadpool(parse_document, data, file_type)
    except ParseError as exc:
        raise DocumentValidationError([str(exc)]) from exc
    header = extract_header_metadata(parsed.full_text)
    if "title" not in header and parsed.title:
        header["title"] = parsed.title
    metadata = build_metadata(form, header, get_kb_config().type_codes)

    document = await db.scalar(select(Document).where(Document.doc_code == metadata.doc_code))
    if document is None:
        document = Document(
            doc_code=metadata.doc_code, title=metadata.title, doc_type=metadata.doc_type
        )
        db.add(document)
        await db.flush()
    else:
        duplicate_version = await db.scalar(
            select(DocumentVersion.id).where(
                DocumentVersion.document_id == document.id,
                DocumentVersion.version == metadata.version,
            )
        )
        if duplicate_version is not None:
            raise DuplicateDocumentError(
                f"{metadata.doc_code} version {metadata.version} already exists. "
                "Upload a new version number instead."
            )
        if document.doc_type != metadata.doc_type:
            raise DocumentValidationError(
                [
                    f"doc_type: {metadata.doc_code} is registered as '{document.doc_type}', "
                    f"not '{metadata.doc_type}'."
                ]
            )
        document.title = metadata.title

    storage_key = (
        f"kb/{metadata.doc_code}/{metadata.version}/{digest[:12]}-{safe_filename(filename)}"
    )
    await run_in_threadpool(storage.put, storage_key, data, MEDIA_TYPES[file_type])

    version = DocumentVersion(
        document_id=document.id,
        version=metadata.version,
        status=VersionStatus.DRAFT,
        activate_on_ready=activate,
        effective_date=metadata.effective_date,
        expiry_date=metadata.expiry_date,
        file_name=safe_filename(filename),
        media_type=MEDIA_TYPES[file_type],
        size_bytes=len(data),
        sha256=digest,
        storage_key=storage_key,
        ingest_status=IngestStatus.PENDING,
        uploaded_by_id=actor.id if actor else None,
    )
    db.add(version)
    await db.flush()
    await audit.record(
        db,
        "document_version.uploaded",
        "document_version",
        version.id,
        actor_user_id=actor.id if actor else None,
        after={**metadata.model_dump(mode="json"), "file": version.file_name, "activate": activate},
    )
    await db.commit()
    if enqueue:
        _safe_enqueue(version.id)
    return version


async def activate_version(db: AsyncSession, version: DocumentVersion, actor: User) -> None:
    siblings = (
        await db.scalars(
            select(DocumentVersion).where(DocumentVersion.document_id == version.document_id)
        )
    ).all()
    changes = plan_activation([to_state(v) for v in siblings], version.id, date.today())
    by_id = {v.id: v for v in siblings}
    for vid, status in changes.items():
        if vid != version.id:
            by_id[vid].status = status
    await db.flush()
    if version.id in changes:
        version.status = changes[version.id]
    await audit.record(
        db,
        "document_version.activated",
        "document_version",
        version.id,
        actor_user_id=actor.id,
        after={str(k): v for k, v in changes.items()},
    )
    if changes.get(version.id) == "active":
        superseded = superseded_by(changes, list(siblings))
        await db.run_sync(
            lambda session: flag_affected_complaints(
                session, version.document_id, superseded, version.version, actor.id
            )
        )
    await db.commit()


async def retire_version(db: AsyncSession, version: DocumentVersion, actor: User) -> None:
    changes = plan_retirement(to_state(version))
    version.status = changes[version.id]
    await audit.record(
        db,
        "document_version.retired",
        "document_version",
        version.id,
        actor_user_id=actor.id,
        after={"status": version.status},
    )
    await db.commit()


async def reprocess_version(db: AsyncSession, version: DocumentVersion, actor: User) -> None:
    version.ingest_status = IngestStatus.PENDING
    version.ingest_error = None
    await audit.record(
        db,
        "document_version.reprocess_requested",
        "document_version",
        version.id,
        actor_user_id=actor.id,
    )
    await db.commit()
    _safe_enqueue(version.id)
