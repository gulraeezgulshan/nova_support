"""Preview (check every row without writing) and run (file each row through the intake)."""

import csv
import hashlib
import io
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bulk_import.reader import escape_cell, read_rows
from complaint_processing.customers import customer_for_email
from complaint_processing.detectors import detect_signals
from complaint_processing.preprocessing import content_hash
from complaint_processing.service import (
    ComplaintInput,
    ComplaintValidationError,
    DuplicateComplaintError,
    safe_enqueue_analysis,
    submit_complaint,
    validate_input,
)
from database import audit
from database.models import Complaint, ComplaintStatus, Customer, ImportBatch, Order, User
from src.core.logging import get_logger

log = get_logger(__name__)
PREVIEW_TTL = timedelta(hours=24)
PROGRESS_EVERY = 10
DEFAULT_CHANNEL = "phone_callback"
INJECTION_NOTE = "Contains instructions aimed at the AI; they will be treated as complaint text."


def enqueue_run(batch_id: uuid.UUID) -> None:
    """Hand the import to a worker. Tests replace this."""
    from bulk_import.tasks import run_import

    run_import.delay(str(batch_id))


def received_at(value: str) -> datetime:
    """'2026-09-20' (noon UTC) or an ISO date-time; naive times are taken as UTC."""
    if "T" in value or " " in value:
        parsed = datetime.fromisoformat(value)
    else:
        parsed = datetime.combine(date.fromisoformat(value), time(12))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _input(values: dict[str, str]) -> ComplaintInput:
    return ComplaintInput(
        title=values.get("title", ""),
        description=values.get("description", ""),
        order_ref=values.get("order_ref"),
        channel=values.get("channel") or DEFAULT_CHANNEL,
        requested_resolution=values.get("requested_resolution"),
    )


async def _check_row(
    db: AsyncSession, values: dict[str, str], seen: set[tuple[str, str]]
) -> dict[str, Any]:
    errors: list[str] = []
    notes: list[str] = []
    email = values.get("customer_email", "").strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        errors.append("customer_email is not a valid e-mail address.")
    try:
        clean, warnings = validate_input(_input(values))
    except ComplaintValidationError as exc:
        return {"values": values, "status": "error", "messages": errors + exc.issues}
    notes += warnings
    if values.get("received_at"):
        try:
            if received_at(values["received_at"]) > datetime.now(UTC):
                errors.append("received_at is in the future.")
        except ValueError:
            errors.append("received_at must be a date like 2026-09-20 or 2026-09-20T10:30.")
    digest = content_hash(clean.title, clean.description)
    if (email, digest) in seen:
        errors.append("Duplicate of an earlier row in this file.")
    seen.add((email, digest))
    customer = await db.scalar(select(Customer).where(func.lower(Customer.email) == email).limit(1))
    if clean.order_ref:
        owned = customer is not None and await db.scalar(
            select(Order.id).where(
                Order.order_ref == clean.order_ref, Order.customer_id == customer.id
            )
        )
        if not owned:
            errors.append(f"Order {clean.order_ref} was not found for this customer.")
    if customer is not None and await db.scalar(
        select(Complaint.complaint_ref).where(
            Complaint.customer_id == customer.id,
            Complaint.content_hash == digest,
            Complaint.status != ComplaintStatus.CLOSED,
        )
    ):
        errors.append("Duplicate of a complaint already on file.")
    if detect_signals(f"{clean.title}\n{clean.description}").get("prompt_injection"):
        notes.append(INJECTION_NOTE)
    status = "error" if errors else "warning" if notes else "ready"
    return {"values": values, "status": status, "messages": errors + notes}


async def preview(
    db: AsyncSession, *, filename: str, data: bytes, user: User
) -> tuple[ImportBatch, bool, list[str]]:
    """Check every row; stores the batch as `previewed`. Returns (batch, seen before, unknown)."""
    rows, unknown = read_rows(filename, data)
    sha = hashlib.sha256(data).hexdigest()
    previously = (
        await db.scalar(
            select(ImportBatch.id)
            .where(ImportBatch.sha256 == sha, ImportBatch.status == "done")
            .limit(1)
        )
        is not None
    )
    seen: set[tuple[str, str]] = set()
    checked = [await _check_row(db, values, seen) for values in rows]
    batch = ImportBatch(
        filename=filename[:200],
        sha256=sha,
        uploaded_by_id=user.id,
        status="previewed",
        total=len(checked),
        rows=checked,
    )
    db.add(batch)
    await db.flush()
    await audit.record(
        db,
        "import.previewed",
        "import",
        batch.id,
        actor_user_id=user.id,
        after={"file": batch.filename, "rows": len(checked)},
    )
    await db.commit()
    return batch, previously, unknown


def expired(batch: ImportBatch, now: datetime | None = None) -> bool:
    return (now or datetime.now(UTC)) - batch.created_at > PREVIEW_TTL


async def _save_progress(
    db: AsyncSession, batch_id: uuid.UUID, rows: list[dict[str, Any]], counts: dict[str, int]
) -> ImportBatch:
    batch = await db.get(ImportBatch, batch_id, populate_existing=True)
    if batch is None:
        raise ValueError(f"Import {batch_id} not found")
    batch.rows = [dict(r) for r in rows]
    batch.created, batch.skipped, batch.failed = (
        counts["created"],
        counts["skipped"],
        counts["failed"],
    )
    await db.commit()
    return batch


async def run(db: AsyncSession, batch_id: uuid.UUID | str) -> ImportBatch:
    """File the ready and warning rows through the normal intake (source "upload").

    Each row is saved on its own (a failing row never stops the others) and progress is saved
    every PROGRESS_EVERY rows, so the page can show it and nothing done is lost.
    """
    batch_uuid = uuid.UUID(str(batch_id))
    batch = await db.get(ImportBatch, batch_uuid)
    if batch is None:
        raise ValueError(f"Import {batch_id} not found")
    uploader = batch.uploaded_by_id
    rows = [dict(row) for row in batch.rows]
    counts = {"created": 0, "skipped": 0, "failed": 0}
    for index, row in enumerate(rows, start=1):
        if row["status"] == "error":
            counts["skipped"] += 1
        else:
            values = row["values"]
            try:
                customer = await customer_for_email(
                    db, values["customer_email"], values.get("customer_name")
                )
                complaint = await submit_complaint(
                    db,
                    customer=customer,
                    submitted_by=None,
                    source="upload",
                    enqueue=False,
                    commit=False,
                    created_at=received_at(values["received_at"])
                    if values.get("received_at")
                    else None,
                    external_ref=(values.get("external_ref") or "")[:40] or None,
                    data=_input(values),
                )
                complaint.import_batch_id = batch_uuid
                await db.commit()
                safe_enqueue_analysis(complaint.id, None)
                row["result"], row["reference"] = "created", complaint.complaint_ref
                counts["created"] += 1
            except (ComplaintValidationError, DuplicateComplaintError) as exc:
                await db.rollback()
                row["result"], row["reason"] = "failed", str(exc)
                counts["failed"] += 1
            except Exception as exc:  # any other problem fails this row only
                await db.rollback()
                log.error("import.row_failed", batch=str(batch_uuid), row=index, error=str(exc))
                row["result"], row["reason"] = "failed", f"Unexpected error: {exc}"
                counts["failed"] += 1
        if index % PROGRESS_EVERY == 0:
            await _save_progress(db, batch_uuid, rows, counts)
    batch = await _save_progress(db, batch_uuid, rows, counts)
    batch.status, batch.finished_at = "done", datetime.now(UTC)
    await audit.record(
        db, "import.completed", "import", batch_uuid, actor_user_id=uploader, after=counts
    )
    await db.commit()
    return batch


async def mark_failed(db: AsyncSession, batch_id: uuid.UUID | str) -> None:
    """A run that crashed as a whole (e.g. the database went away) is shown as failed."""
    batch = await db.get(ImportBatch, uuid.UUID(str(batch_id)), populate_existing=True)
    if batch is not None and batch.status == "running":
        batch.status, batch.finished_at = "failed", datetime.now(UTC)
        await db.commit()


def result_csv(batch: ImportBatch) -> bytes:
    """Row number (as in the spreadsheet), outcome, reference or reason — formula-safe."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["row", "status", "reference", "reason"])
    for number, row in enumerate(batch.rows, start=2):  # row 1 is the header
        status = row.get("result") or row["status"]
        reason = row.get("reason") or "; ".join(row.get("messages", []))
        writer.writerow([number, status, row.get("reference", ""), escape_cell(reason)])
    return buffer.getvalue().encode("utf-8")
