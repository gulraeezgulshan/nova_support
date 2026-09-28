"""Knowledge-base document endpoints."""

import uuid
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Chunk, Document, DocumentVersion, Role, User
from database.session import get_db
from knowledge_base import service
from knowledge_base.config import get_kb_config
from knowledge_base.embeddings import Embedder, get_embedder
from knowledge_base.retrieval import search_chunks
from security.dependencies import STAFF_ROLES, require_roles
from src.api.schemas import (
    ChunkOut,
    DocumentOut,
    DocumentTypeOut,
    DocumentVersionOut,
    ErrorResponse,
    SearchResultOut,
)
from src.core.config import Settings, get_settings
from src.core.storage import Storage, get_storage, safe_filename

router = APIRouter(tags=["knowledge-base"])
staff = require_roles(*STAFF_ROLES)
admin_only = require_roles(Role.ADMIN)


async def _get_version(db: AsyncSession, version_id: uuid.UUID) -> DocumentVersion:
    version = await db.get(DocumentVersion, version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document version not found")
    return version


@router.get("/documents/types", response_model=list[DocumentTypeOut])
async def list_document_types(_: User = Depends(staff)) -> list[DocumentTypeOut]:
    return [DocumentTypeOut(**t.model_dump()) for t in get_kb_config().document_types]


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    _: User = Depends(staff), db: AsyncSession = Depends(get_db)
) -> list[Document]:
    return list((await db.scalars(select(Document).order_by(Document.doc_code))).all())


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID, _: User = Depends(staff), db: AsyncSession = Depends(get_db)
) -> Document:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document


@router.post(
    "/documents/upload",
    response_model=DocumentVersionOut,
    status_code=status.HTTP_202_ACCEPTED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def upload_document(
    file: UploadFile = File(...),
    doc_code: str | None = Form(None, description="Leave empty to read it from the document"),
    title: str | None = Form(None),
    doc_type: str | None = Form(None),
    version: str | None = Form(None),
    effective_date: date | None = Form(None),
    expiry_date: date | None = Form(None),
    activate: bool = Form(True, description="Make this the active version once processed"),
    actor: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> DocumentVersion:
    # Read one byte past the limit so oversized files are rejected without loading more.
    data = await file.read(settings.max_upload_bytes + 1)
    form = {
        "doc_code": doc_code,
        "title": title,
        "doc_type": doc_type,
        "version": version,
        "effective_date": effective_date.isoformat() if effective_date else None,
        "expiry_date": expiry_date.isoformat() if expiry_date else None,
    }
    return await service.upload_document(
        db,
        filename=file.filename or "upload",
        data=data,
        form=form,
        activate=activate,
        actor=actor,
        storage=storage,
        settings=settings,
    )


# Types a browser shows safely in a tab; everything else (e.g. Word) is downloaded.
INLINE_TYPES = {"application/pdf", "text/plain", "text/markdown"}


def content_disposition(media_type: str, file_name: str) -> str:
    kind = "inline" if media_type.split(";")[0].strip() in INLINE_TYPES else "attachment"
    return f'{kind}; filename="{safe_filename(file_name)}"'


@router.get(
    "/document-versions/{version_id}/file",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def download_version_file(
    version_id: uuid.UUID,
    _: User = Depends(staff),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> Response:
    """The original uploaded file of a document version (staff only)."""
    version = await _get_version(db, version_id)
    data = await run_in_threadpool(storage.get, version.storage_key)
    return Response(
        content=data,
        media_type=version.media_type,
        headers={
            "Content-Disposition": content_disposition(version.media_type, version.file_name),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/document-versions/{version_id}/chunks", response_model=list[ChunkOut])
async def list_version_chunks(
    version_id: uuid.UUID, _: User = Depends(staff), db: AsyncSession = Depends(get_db)
) -> list[Chunk]:
    await _get_version(db, version_id)
    return list(
        (
            await db.scalars(
                select(Chunk).where(Chunk.document_version_id == version_id).order_by(Chunk.ordinal)
            )
        ).all()
    )


@router.post("/document-versions/{version_id}/activate", response_model=DocumentVersionOut)
async def activate_version(
    version_id: uuid.UUID, actor: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> DocumentVersion:
    version = await _get_version(db, version_id)
    await service.activate_version(db, version, actor)
    return version


@router.post("/document-versions/{version_id}/retire", response_model=DocumentVersionOut)
async def retire_version(
    version_id: uuid.UUID, actor: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> DocumentVersion:
    version = await _get_version(db, version_id)
    await service.retire_version(db, version, actor)
    return version


@router.post(
    "/document-versions/{version_id}/reprocess",
    response_model=DocumentVersionOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reprocess_version(
    version_id: uuid.UUID, actor: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> DocumentVersion:
    version = await _get_version(db, version_id)
    await service.reprocess_version(db, version, actor)
    return version


@router.get("/knowledge-base/search", response_model=list[SearchResultOut])
async def search_knowledge_base(
    q: str = Query(min_length=2, max_length=500),
    limit: int = Query(8, ge=1, le=25),
    _: User = Depends(staff),
    db: AsyncSession = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
) -> list[SearchResultOut]:
    results = await search_chunks(db, q, embedder, limit)
    return [SearchResultOut(**r.__dict__) for r in results]
