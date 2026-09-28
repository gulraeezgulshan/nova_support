"""Complaint intake: validation (SRS Step 10), pre-processing (Step 11), duplicate detection
(Step 52), deterministic signals, storage and hand-off to the analysis pipeline."""

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app_settings
from complaint_processing.detectors import detect_signals
from complaint_processing.duplicates import find_similar
from complaint_processing.preprocessing import (
    content_hash,
    extract_entities,
    normalize_for_matching,
    sanitize_text,
)
from complaint_processing.sensitive import redact
from database import audit
from database.models import (
    COMPLAINT_REF_SEQ,
    CUSTOMER_REF_SEQ,
    Complaint,
    ComplaintEvent,
    ComplaintStatus,
    Customer,
    CustomerType,
    Order,
    User,
)
from knowledge_base.embeddings import get_embedder
from src.core.domain import analysis_config
from src.core.logging import get_logger

log = get_logger(__name__)

MIN_TITLE_CHARS = 5
MIN_DESCRIPTION_CHARS = 20
MIN_DESCRIPTION_WORDS = 5
MAX_DESCRIPTION_CHARS = 5000
DUPLICATE_WINDOW_DAYS = 30
ORDER_REF_FORMAT = re.compile(r"^ORD-\d{6}$")
COMPLAINT_REF_FORMAT = re.compile(r"^CMP-\d{6}$")
ORDER_WORDS = re.compile(r"\b(order|parcel|package|delivery|delivered|charged|refund|invoice)\b")


@dataclass
class ComplaintValidationError(Exception):
    issues: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return "; ".join(self.issues)


class DuplicateComplaintError(Exception):
    def __init__(self, existing_ref: str):
        super().__init__(
            f"This complaint was already submitted as {existing_ref}. "
            "Add new information to that complaint instead."
        )
        self.existing_ref = existing_ref


@dataclass
class ComplaintInput:
    title: str
    description: str
    product_service: str | None = None
    order_ref: str | None = None
    previous_complaint_ref: str | None = None
    channel: str = "web_form"
    preferred_contact_channel: str | None = None
    requested_resolution: str | None = None


def enqueue_analysis(complaint_id: uuid.UUID, triggered_by: uuid.UUID | None = None) -> None:
    """Hand the complaint to a Celery worker (analysis + validation). Tests replace this."""
    from complaint_processing.tasks import process_complaint

    process_complaint.delay(str(complaint_id), str(triggered_by) if triggered_by else None)


def safe_enqueue_analysis(complaint_id: uuid.UUID, triggered_by: uuid.UUID | None = None) -> None:
    try:
        enqueue_analysis(complaint_id, triggered_by)
    except Exception as exc:  # broker down: complaint stays "new"; staff can re-run analysis
        log.error("analysis.enqueue_failed", complaint_id=str(complaint_id), error=str(exc))


def enqueue_automatic(complaint_id: uuid.UUID, triggered_by: uuid.UUID | None = None) -> bool:
    """Analysis started by intake (web, chat, e-mail, bulk import), unless switched off."""
    if not app_settings.runtime().ai.auto_analysis:
        log.info("analysis.automatic_off", complaint_id=str(complaint_id))
        return False
    safe_enqueue_analysis(complaint_id, triggered_by)
    return True


async def next_ref(db: AsyncSession, prefix: str, sequence: object) -> str:
    value = await db.scalar(select(func.nextval(sequence.name)))  # type: ignore[attr-defined]
    return f"{prefix}-{int(value or 0):06d}"


async def get_or_create_customer(db: AsyncSession, user: User) -> Customer:
    customer = await db.scalar(select(Customer).where(Customer.user_id == user.id))
    if customer is None:
        customer = Customer(
            customer_ref=await next_ref(db, "CUST", CUSTOMER_REF_SEQ),
            full_name=user.full_name or user.email or "Customer",
            email=user.email,
            customer_type=CustomerType.STANDARD,
            user_id=user.id,
        )
        db.add(customer)
        await db.flush()
    return customer


def validate_input(data: ComplaintInput) -> tuple[ComplaintInput, list[str]]:
    """Return the sanitised input and non-blocking warnings, or raise with every problem."""
    issues: list[str] = []
    # Card numbers, passwords and ID numbers are removed before anything is stored or sent on.
    redactions = [redact(sanitize_text(v)) for v in (data.title, data.description,
                                                      data.requested_resolution or "")]  # fmt: skip
    title, description, requested = (r.text for r in redactions)
    removed = list(dict.fromkeys(kind for r in redactions for kind in r.kinds))
    config = analysis_config()

    if len(title) < MIN_TITLE_CHARS:
        issues.append(f"Title must be at least {MIN_TITLE_CHARS} characters.")
    if not description:
        issues.append("Description is required.")
    elif (
        len(description) < MIN_DESCRIPTION_CHARS or len(description.split()) < MIN_DESCRIPTION_WORDS
    ):
        issues.append(
            "Description is too short to act on. Please describe what happened, "
            "when, and what you would like us to do."
        )
    if len(description) > MAX_DESCRIPTION_CHARS:
        issues.append(f"Description must be at most {MAX_DESCRIPTION_CHARS} characters.")
    order_ref = (data.order_ref or "").strip().upper() or None
    if order_ref and not ORDER_REF_FORMAT.match(order_ref):
        issues.append("Order reference must look like ORD-240001.")
    previous_ref = (data.previous_complaint_ref or "").strip().upper() or None
    if previous_ref and not COMPLAINT_REF_FORMAT.match(previous_ref):
        issues.append("Previous complaint reference must look like CMP-000123.")
    if data.channel not in config.complaint_channels:
        issues.append(f"Unknown channel '{data.channel}'.")
    if (
        data.preferred_contact_channel
        and data.preferred_contact_channel not in config.complaint_channels
    ):
        issues.append(f"Unknown contact channel '{data.preferred_contact_channel}'.")
    if issues:
        raise ComplaintValidationError(issues)

    warnings = []
    if removed:
        warnings.append(f"Sensitive data removed: {', '.join(removed)}.")
    if not order_ref and ORDER_WORDS.search(description.lower()):
        warnings.append("No order reference provided.")
    clean = ComplaintInput(
        title=title[:200],
        description=description,
        product_service=sanitize_text(data.product_service or "") or None,
        order_ref=order_ref,
        previous_complaint_ref=previous_ref,
        channel=data.channel,
        preferred_contact_channel=data.preferred_contact_channel,
        requested_resolution=requested or None,
    )
    return clean, warnings


async def submit_complaint(
    db: AsyncSession,
    *,
    customer: Customer,
    data: ComplaintInput,
    submitted_by: User | None,
    source: str = "portal",
    enqueue: bool = True,
    created_at: datetime | None = None,
    external_ref: str | None = None,
    commit: bool = True,
) -> Complaint:
    """File a complaint. With `commit=False` the caller commits (and enqueues analysis after
    that), so the complaint and the caller's own rows are saved together or not at all."""
    if not commit and enqueue:
        raise ValueError("enqueue=True needs commit=True (analysis must run after the commit)")
    clean, warnings = validate_input(data)
    issues: list[str] = []

    order = None
    if clean.order_ref:
        order = await db.scalar(select(Order).where(Order.order_ref == clean.order_ref))
        if order is None or order.customer_id != customer.id:
            issues.append(f"Order {clean.order_ref} was not found on this customer's account.")
    previous = None
    if clean.previous_complaint_ref:
        previous = await db.scalar(
            select(Complaint).where(Complaint.complaint_ref == clean.previous_complaint_ref)
        )
        if previous is None or previous.customer_id != customer.id:
            issues.append(f"Complaint {clean.previous_complaint_ref} was not found.")
    if issues:
        raise ComplaintValidationError(issues)

    digest = content_hash(clean.title, clean.description)
    now = created_at or datetime.now(UTC)
    duplicate = await db.scalar(
        select(Complaint.complaint_ref).where(
            Complaint.customer_id == customer.id,
            Complaint.content_hash == digest,
            Complaint.created_at >= now - timedelta(days=DUPLICATE_WINDOW_DAYS),
            Complaint.status != ComplaintStatus.CLOSED,
        )
    )
    if duplicate:
        raise DuplicateComplaintError(duplicate)

    full_text = "\n".join(
        filter(None, [clean.title, clean.description, clean.requested_resolution])
    )
    normalized = normalize_for_matching(full_text)
    embedding = await run_in_threadpool(get_embedder().embed_query, full_text)
    similar = await find_similar(db, customer.id, normalized, embedding, now)
    if similar is not None:
        label = "near-duplicate of" if similar.kind == "near_duplicate" else "possibly related to"
        warnings.append(f"Looks like a {label} {similar.complaint_ref} ({similar.similarity:.0%}).")
    complaint = Complaint(
        complaint_ref=await next_ref(db, "CMP", COMPLAINT_REF_SEQ),
        # Set relationships directly: async sessions cannot lazy-load them later.
        customer=customer,
        order=order,
        submitted_by_id=submitted_by.id if submitted_by else None,
        title=clean.title,
        description=clean.description,
        normalized_text=normalized,
        embedding=embedding,
        duplicate_of_id=similar.complaint_id
        if similar and similar.kind == "near_duplicate"
        else None,
        related_complaint_id=similar.complaint_id
        if similar and similar.kind == "related"
        else None,
        similarity=similar.similarity if similar else None,
        content_hash=digest,
        product_service=clean.product_service or (order.product_name if order else None),
        channel=clean.channel,
        preferred_contact_channel=clean.preferred_contact_channel,
        requested_resolution=clean.requested_resolution,
        previous_complaint_id=previous.id if previous else None,
        source=source,
        external_ref=external_ref,
        status=ComplaintStatus.NEW,
        entities=extract_entities(full_text),
        signals=detect_signals(full_text),
        intake_warnings=warnings,
    )
    if created_at:
        complaint.created_at = created_at
    db.add(complaint)
    await db.flush()
    db.add(
        ComplaintEvent(
            complaint_id=complaint.id,
            event_type="submitted",
            to_status=ComplaintStatus.NEW,
            message="Complaint received.",
            actor_user_id=submitted_by.id if submitted_by else None,
        )
    )
    await audit.record(
        db,
        "complaint.submitted",
        "complaint",
        complaint.id,
        actor_user_id=submitted_by.id if submitted_by else None,
        after={"ref": complaint.complaint_ref, "signals": sorted(complaint.signals)},
    )
    if not commit:
        await db.flush()
        return complaint
    await db.commit()
    if enqueue:
        enqueue_automatic(complaint.id, submitted_by.id if submitted_by else None)
    return complaint
