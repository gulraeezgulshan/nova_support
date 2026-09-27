"""Supporting documents on a complaint: the owning customer and staff only."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from complaint_processing.attachments import (
    MAX_ATTACHMENT_BYTES,
    AttachmentError,
    add_attachment,
    remove_attachment,
)
from database.models import ComplaintAttachment, User
from database.session import get_db
from security.dependencies import get_current_user
from src.api.routes.complaints import _is_staff, _load_for
from src.api.schemas import AttachmentOut
from src.core.storage import Storage, get_storage

router = APIRouter(tags=["attachments"])


async def _attachment(
    db: AsyncSession, ref: str, attachment_id: uuid.UUID, user: User
) -> ComplaintAttachment:
    complaint = await _load_for(db, ref, user)
    attachment = await db.get(ComplaintAttachment, attachment_id)
    if attachment is None or attachment.complaint_id != complaint.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    return attachment


@router.get("/complaints/{ref}/attachments", response_model=list[AttachmentOut])
async def list_complaint_attachments(
    ref: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ComplaintAttachment]:
    return list((await _load_for(db, ref, user)).attachments)


@router.post(
    "/complaints/{ref}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_complaint_attachment(
    ref: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> ComplaintAttachment:
    """Add a photo or PDF (the complaint's customer, or staff)."""
    complaint = await _load_for(db, ref, user)
    data = await file.read(MAX_ATTACHMENT_BYTES + 1)
    try:
        attachment = await add_attachment(
            db,
            complaint,
            filename=file.filename or "attachment",
            data=data,
            source="staff" if _is_staff(user) else "customer",
            uploaded_by=user,
            storage=storage,
        )
    except AttachmentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    await db.commit()
    return attachment


@router.get(
    "/complaints/{ref}/attachments/{attachment_id}",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def download_complaint_attachment(
    ref: str,
    attachment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> Response:
    attachment = await _attachment(db, ref, attachment_id, user)
    return Response(
        content=storage.get(attachment.storage_key),
        media_type=attachment.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{attachment.filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete(
    "/complaints/{ref}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_complaint_attachment(
    ref: str,
    attachment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> Response:
    """Staff only: remove a supporting document."""
    attachment = await _attachment(db, ref, attachment_id, user)
    if not _is_staff(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only staff can remove documents")
    await remove_attachment(db, attachment, user, storage)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
