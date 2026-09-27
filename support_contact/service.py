"""Contact us: order problems become complaints (normal intake), everything else an enquiry."""

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from complaint_processing.preprocessing import sanitize_text
from complaint_processing.sensitive import redact
from complaint_processing.service import (
    MIN_TITLE_CHARS,
    ComplaintInput,
    get_or_create_customer,
    next_ref,
    submit_complaint,
)
from database import audit
from database.models import (
    ENQUIRY_REF_SEQ,
    Complaint,
    Customer,
    Enquiry,
    EnquiryStatus,
    NewsletterSubscriber,
    User,
)

COMPLAINT_TOPIC = "order_problem"
Topic = Literal["order_problem", "product_question", "business", "feedback", "other"]


class ContactError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def clean(text: str) -> str:
    """Sanitised, with card numbers, passwords and ID numbers redacted."""
    return redact(sanitize_text(text)).text


TITLE_CHARS = 70


def _title(message: str) -> str:
    """A short title from the (already redacted) message: its first line, or the start of
    the whole message when that line is too short, cut at a word boundary."""
    text = clean(message).strip()
    first_line = text.split("\n")[0].strip()
    source = first_line if len(first_line) >= MIN_TITLE_CHARS else " ".join(text.split())
    if len(source) > TITLE_CHARS:
        cut = source[:TITLE_CHARS]
        source = cut.rsplit(" ", 1)[0] if " " in cut else cut
    return source if len(source) >= MIN_TITLE_CHARS else "Problem with an order"


async def submit_contact(
    db: AsyncSession,
    user: User | None,
    *,
    name: str,
    email: str,
    topic: Topic,
    message: str,
    order_ref: str | None,
) -> tuple[Literal["complaint", "enquiry"], str]:
    """File a contact form. Returns (kind, reference)."""
    if topic == COMPLAINT_TOPIC:
        if user is None:
            raise ContactError(
                401,
                "Please sign in to report a problem with an order, so we can look at your orders.",
            )
        customer = await get_or_create_customer(db, user)
        complaint = await submit_complaint(
            db,
            customer=customer,
            submitted_by=user,
            data=ComplaintInput(
                title=_title(message), description=message, order_ref=order_ref, channel="web_form"
            ),
        )
        return "complaint", complaint.complaint_ref

    account = await get_or_create_customer(db, user) if user else None
    enquiry = Enquiry(
        ref=await next_ref(db, "ENQ", ENQUIRY_REF_SEQ),
        name=clean(name)[:200],
        email=email.strip().lower(),
        topic=topic,
        message=clean(message),
        user_id=user.id if user else None,
        customer_id=account.id if account else None,
    )
    db.add(enquiry)
    await audit.record(
        db,
        "enquiry.received",
        "enquiry",
        enquiry.ref,
        actor_user_id=user.id if user else None,
        after={"topic": topic},
    )
    await db.commit()
    return "enquiry", enquiry.ref


async def set_status(
    db: AsyncSession, enquiry: Enquiry, status: EnquiryStatus, actor: User
) -> None:
    before = enquiry.status
    enquiry.status = status
    handled = status == EnquiryStatus.HANDLED
    enquiry.handled_by_id = actor.id if handled else None
    enquiry.handled_at = datetime.now(UTC) if handled else None
    await audit.record(
        db,
        "enquiry.status_changed",
        "enquiry",
        enquiry.ref,
        actor_user_id=actor.id,
        before={"status": before},
        after={"status": status},
    )
    await db.commit()


async def convert(db: AsyncSession, enquiry: Enquiry, actor: User) -> Complaint:
    """Turn an enquiry from a signed-in customer into a complaint (once)."""
    if enquiry.customer_id is None:
        raise ContactError(
            422, "Only enquiries sent by a signed-in customer can become complaints."
        )
    if enquiry.complaint_id is not None:
        raise ContactError(422, "This enquiry has already been turned into a complaint.")
    customer = await db.get(Customer, enquiry.customer_id)
    if customer is None:  # pragma: no cover - foreign key guarantees it
        raise ContactError(422, "The customer for this enquiry no longer exists.")
    complaint = await submit_complaint(
        db,
        customer=customer,
        submitted_by=actor,
        data=ComplaintInput(
            title=f"From enquiry {enquiry.ref}", description=enquiry.message, channel="web_form"
        ),
    )
    enquiry.complaint_id = complaint.id
    enquiry.status = EnquiryStatus.HANDLED
    enquiry.handled_by_id, enquiry.handled_at = actor.id, datetime.now(UTC)
    await audit.record(
        db,
        "enquiry.converted",
        "enquiry",
        enquiry.ref,
        actor_user_id=actor.id,
        after={"complaint": complaint.complaint_ref},
    )
    await db.commit()
    return complaint


async def subscribe(db: AsyncSession, email: str, source: str) -> None:
    """Record a newsletter sign-up once (repeat sign-ups are ignored)."""
    await db.execute(
        insert(NewsletterSubscriber)
        .values(email=email.strip().lower(), source=source)
        .on_conflict_do_nothing(index_elements=["email"])
    )
    await db.commit()
