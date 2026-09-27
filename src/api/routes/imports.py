"""Bulk complaint upload (managers and administrators): template, preview, run, result."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bulk_import import service
from bulk_import.reader import MAX_BYTES, ImportFileError, template_csv, template_xlsx
from database import audit
from database.models import ImportBatch, Role, User
from database.session import get_db
from security.dependencies import require_roles
from src.api.schemas import ImportBatchOut, ImportDetailOut, ImportPreviewOut, ImportRowOut

router = APIRouter(tags=["imports"])
managers = require_roles(Role.MANAGER, Role.ADMIN)
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _rows(batch: ImportBatch) -> list[ImportRowOut]:
    return [ImportRowOut(row=i, **row) for i, row in enumerate(batch.rows, start=2)]


def _summary(batch: ImportBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "filename": batch.filename,
        "status": batch.status,
        "total": batch.total,
        "created": batch.created,
        "skipped": batch.skipped,
        "failed": batch.failed,
        "created_at": batch.created_at,
        "finished_at": batch.finished_at,
    }


async def _batch(db: AsyncSession, batch_id: uuid.UUID) -> ImportBatch:
    batch = await db.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import not found")
    return batch


@router.get("/imports/template.csv", response_class=Response)
async def import_template_csv(_: User = Depends(managers)) -> Response:
    return Response(
        template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="complaints-template.csv"'},
    )


@router.get("/imports/template.xlsx", response_class=Response)
async def import_template_xlsx(_: User = Depends(managers)) -> Response:
    return Response(
        template_xlsx(),
        media_type=XLSX,
        headers={"Content-Disposition": 'attachment; filename="complaints-template.xlsx"'},
    )


@router.post(
    "/imports/preview", response_model=ImportPreviewOut, status_code=status.HTTP_201_CREATED
)
async def preview_import(
    file: UploadFile = File(...),
    user: User = Depends(managers),
    db: AsyncSession = Depends(get_db),
) -> ImportPreviewOut:
    """Check every row with the intake's own rules; nothing is filed yet."""
    data = await file.read(MAX_BYTES + 1)
    try:
        batch, previously, unknown = await service.preview(
            db, filename=file.filename or "upload.csv", data=data, user=user
        )
    except ImportFileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return ImportPreviewOut(
        **_summary(batch),
        rows=_rows(batch),
        previously_imported=previously,
        unknown_columns=unknown,
    )


@router.post(
    "/imports/{batch_id}/run", response_model=ImportBatchOut, status_code=status.HTTP_202_ACCEPTED
)
async def run_import(
    batch_id: uuid.UUID, user: User = Depends(managers), db: AsyncSession = Depends(get_db)
) -> ImportBatchOut:
    """Import the ready and warning rows in the background."""
    batch = await _batch(db, batch_id)
    if batch.status != "previewed":
        raise HTTPException(status.HTTP_409_CONFLICT, "This file has already been imported.")
    if service.expired(batch, datetime.now(UTC)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This preview is more than 24 hours old. Preview again."
        )
    claimed = await db.scalar(  # atomic: two quick clicks cannot both start the import
        update(ImportBatch)
        .where(ImportBatch.id == batch.id, ImportBatch.status == "previewed")
        .values(status="running")
        .returning(ImportBatch.id)
    )
    if claimed is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This file has already been imported.")
    await audit.record(db, "import.started", "import", batch.id, actor_user_id=user.id)
    await db.commit()
    try:
        service.enqueue_run(batch.id)
    except Exception as exc:  # broker down: undo the claim so the user can try again
        await db.execute(
            update(ImportBatch).where(ImportBatch.id == batch.id).values(status="previewed")
        )
        await db.commit()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The background worker is not available. Try again in a minute.",
        ) from exc
    await db.refresh(batch)
    return ImportBatchOut(**_summary(batch))


@router.get("/imports", response_model=list[ImportBatchOut])
async def list_imports(
    _: User = Depends(managers), db: AsyncSession = Depends(get_db)
) -> list[ImportBatchOut]:
    batches = await db.scalars(
        select(ImportBatch).order_by(ImportBatch.created_at.desc()).limit(50)
    )
    return [ImportBatchOut(**_summary(b)) for b in batches]


@router.get("/imports/{batch_id}", response_model=ImportDetailOut)
async def get_import(
    batch_id: uuid.UUID, _: User = Depends(managers), db: AsyncSession = Depends(get_db)
) -> ImportDetailOut:
    batch = await _batch(db, batch_id)
    return ImportDetailOut(**_summary(batch), rows=_rows(batch))


@router.get("/imports/{batch_id}/result.csv", response_class=Response)
async def import_result(
    batch_id: uuid.UUID, _: User = Depends(managers), db: AsyncSession = Depends(get_db)
) -> Response:
    batch = await _batch(db, batch_id)
    name = f"import-{batch.created_at:%Y%m%d-%H%M}-result.csv"
    return Response(
        service.result_csv(batch),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
