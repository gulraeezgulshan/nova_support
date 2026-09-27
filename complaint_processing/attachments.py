"""Supporting documents: content-checked photos and PDFs on a complaint."""

import uuid
from collections import Counter
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import audit
from database.models import Complaint, ComplaintAttachment, User
from src.core.storage import Storage, safe_filename
from storefront.images import image_type

MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
MAX_ATTACHMENTS = 5
EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "application/pdf": "pdf",
}
Source = Literal["email", "customer", "staff"]


class AttachmentError(ValueError):
    pass


def file_type(data: bytes) -> str | None:
    """Media type from the file's first bytes (never from its name)."""
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    return image_type(data)


def describe(media_types: list[str]) -> str:
    """'2 photos, 1 PDF' — what the analysis and validation are told about the evidence."""
    counts = Counter("PDF" if t == "application/pdf" else "photo" for t in media_types)
    parts = [
        f"{counts[label]} {label}{'s' if counts[label] > 1 else ''}"
        for label in ("photo", "PDF")
        if counts[label]
    ]
    return ", ".join(parts) or "none"


async def add_attachment(
    db: AsyncSession,
    complaint: Complaint,
    *,
    filename: str,
    data: bytes,
    source: Source,
    uploaded_by: User | None,
    storage: Storage,
) -> ComplaintAttachment:
    """Check and store one file; flushes and audits, the caller commits."""
    if not data:
        raise AttachmentError("The file is empty.")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise AttachmentError("Files must be 5 MB or smaller.")
    media_type = file_type(data)
    if media_type is None:
        raise AttachmentError("Only photos (JPG, PNG, WebP) and PDF files can be attached.")
    count = await db.scalar(
        select(func.count())
        .select_from(ComplaintAttachment)
        .where(ComplaintAttachment.complaint_id == complaint.id)
    )
    if (count or 0) >= MAX_ATTACHMENTS:
        raise AttachmentError(f"A complaint can have at most {MAX_ATTACHMENTS} attachments.")
    attachment_id = uuid.uuid4()
    key = f"complaints/{complaint.id}/{attachment_id}.{EXTENSIONS[media_type]}"
    storage.put(key, data, media_type)
    attachment = ComplaintAttachment(
        id=attachment_id,
        complaint_id=complaint.id,
        filename=safe_filename(filename),
        media_type=media_type,
        size_bytes=len(data),
        storage_key=key,
        source=source,
        uploaded_by_id=uploaded_by.id if uploaded_by else None,
    )
    db.add(attachment)
    await db.flush()
    await audit.record(
        db,
        "attachment.added",
        "complaint",
        complaint.id,
        actor_user_id=uploaded_by.id if uploaded_by else None,
        after={"file": attachment.filename, "source": source},
    )
    return attachment


async def remove_attachment(
    db: AsyncSession, attachment: ComplaintAttachment, actor: User, storage: Storage
) -> None:
    await audit.record(
        db,
        "attachment.removed",
        "complaint",
        attachment.complaint_id,
        actor_user_id=actor.id,
        before={"file": attachment.filename},
    )
    await db.delete(attachment)
    storage.delete(attachment.storage_key)
