"""E-mail complaints: filing, threading, ignoring loops, replies queued once."""

from collections.abc import Callable

import httpx
import pytest
from sqlalchemy import select

from database.models import (
    Complaint,
    ComplaintEvent,
    Customer,
    InboundEmail,
    OutboundEmail,
    Role,
    User,
)
from database.session import async_session_factory, sync_session
from email_channel.inbound import process_email
from email_channel.parsing import parse_email
from src.core.storage import get_storage
from tests.emails import build

pytestmark = pytest.mark.db

BODY = "My tablet arrived with a cracked screen and the box was crushed in transit."
OWN = "care@volthaven.test"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 40


async def receive(raw: bytes) -> InboundEmail:
    async with async_session_factory()() as db:
        return await process_email(
            db, parse_email(raw), via="manual", own_address=OWN, storage=get_storage()
        )


def outbound(db: object) -> list[OutboundEmail]:
    return list(
        db.scalars(select(OutboundEmail).order_by(OutboundEmail.created_at))  # type: ignore[attr-defined]
    )


async def test_new_email_files_a_complaint_and_queues_an_acknowledgement(
    client: httpx.AsyncClient,
) -> None:
    raw = build(
        text=f"{BODY} Order ORD-999999.",
        subject="Fwd: Broken tablet",
        attachments=(
            ("photo.png", "image/png", PNG),
            ("virus.exe", "application/octet-stream", b"MZ\x90"),
        ),
    )
    record = await receive(raw)
    assert record.outcome == "filed" and record.complaint_id
    with sync_session() as db:
        complaint = db.get(Complaint, record.complaint_id)
        assert complaint is not None
        assert complaint.channel == "email" and complaint.source == "email"
        assert complaint.title == "Broken tablet" and complaint.order is None  # not theirs
        assert complaint.customer.email == "sara@example.test"
        assert complaint.customer.full_name == "Sara Khan"
        assert [a.media_type for a in complaint.attachments] == ["image/png"]
        skipped = db.scalar(
            select(ComplaintEvent).where(
                ComplaintEvent.complaint_id == complaint.id,
                ComplaintEvent.message.contains("virus.exe"),
            )
        )
        assert skipped is not None and not skipped.customer_visible
        [ack] = outbound(db)
        assert ack.kind == "acknowledgement" and ack.to_address == "sara@example.test"
        assert f"[{complaint.complaint_ref}]" in ack.subject
        assert ack.in_reply_to == "<m1@example.test>" and ack.status == "queued"
        assert complaint.complaint_ref in ack.body
    assert len(client.app.state.analyses) == 1  # type: ignore[attr-defined]


async def test_same_message_is_processed_once(client: httpx.AsyncClient) -> None:
    first = await receive(build(text=BODY))
    again = await receive(build(text=BODY))
    assert again.id == first.id
    with sync_session() as db:
        assert len(db.scalars(select(Complaint)).all()) == 1
        assert len(outbound(db)) == 1


async def test_reply_in_thread_is_appended_without_the_quote(client: httpx.AsyncClient) -> None:
    first = await receive(build(text=BODY))
    with sync_session() as db:
        [ack] = outbound(db)
    quoted = "\n".join(f"> {line}" for line in ack.body.splitlines())
    reply = build(
        text=f"Any update please?\n\nOn Mon, VoltHaven wrote:\n{quoted}",
        subject=f"Re: {ack.subject}",
        message_id="<m2@example.test>",
        in_reply_to=ack.message_id,
        attachments=(("second.png", "image/png", PNG),),
    )
    record = await receive(reply)
    assert record.outcome == "appended" and record.complaint_id == first.complaint_id
    with sync_session() as db:
        event = db.scalar(
            select(ComplaintEvent).where(ComplaintEvent.event_type == "customer_message")
        )
        assert event is not None
        assert event.message == "Customer message (email): Any update please?"
        assert len(db.scalars(select(Complaint)).all()) == 1
        complaint = db.get(Complaint, first.complaint_id)
        assert complaint is not None and len(complaint.attachments) == 1


async def test_thread_reply_from_another_address_is_a_new_complaint(
    client: httpx.AsyncClient,
) -> None:
    first = await receive(build(text=BODY))
    with sync_session() as db:
        [ack] = outbound(db)
    other = build(
        text="Someone else's order arrived smashed and nobody answers my calls at all.",
        sender="Bob <bob@example.test>",
        subject=f"Re: {ack.subject}",
        message_id="<m3@example.test>",
        in_reply_to=ack.message_id,
    )
    record = await receive(other)
    assert record.outcome == "filed" and record.complaint_id != first.complaint_id


@pytest.mark.parametrize(
    "headers",
    [{"Auto-Submitted": "auto-replied"}, {"Precedence": "bulk"}],
    ids=["auto", "bulk"],
)
async def test_automatic_mail_is_ignored_and_never_answered(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    record = await receive(build(text="I am out of the office until Monday.", headers=headers))
    assert record.outcome == "ignored"
    ours = await receive(build(text=BODY, sender=f"VoltHaven <{OWN}>", message_id="<m9@x>"))
    assert ours.outcome == "ignored"
    with sync_session() as db:
        assert outbound(db) == []
        assert db.scalars(select(Complaint)).all() == []


async def test_too_short_and_duplicate_get_an_answer(client: httpx.AsyncClient) -> None:
    short = await receive(build(text="broken", message_id="<s1@x>"))
    assert short.outcome == "rejected" and "too short" in (short.reason or "").lower()
    await receive(build(text=BODY, message_id="<d1@x>"))
    dup = await receive(build(text=BODY, message_id="<d2@x>"))
    assert dup.outcome == "duplicate" and dup.complaint_id
    with sync_session() as db:
        kinds = sorted(o.kind for o in outbound(db))
        assert kinds == ["acknowledgement", "duplicate", "rejected"]


async def test_known_customer_and_their_order_are_linked(
    client: httpx.AsyncClient,
    create_user: Callable[..., User],
    make_token: Callable[..., str],
) -> None:
    user = create_user(Role.CUSTOMER, email="sara@example.test")
    headers = {"Authorization": f"Bearer {make_token(user.clerk_user_id)}"}
    body = {"lines": [{"sku": "VH-TAB-T11", "quantity": 1}]}
    [order] = (await client.post("/api/v1/checkout", headers=headers, json=body)).json()
    record = await receive(build(text=f"{BODY} It was order {order['order_ref']}."))
    with sync_session() as db:
        complaint = db.get(Complaint, record.complaint_id)
        assert complaint is not None and complaint.order is not None
        assert complaint.order.order_ref == order["order_ref"]
        assert len(db.scalars(select(Customer)).all()) == 1


async def test_replies_follow_validation_and_approval_once(client: httpx.AsyncClient) -> None:
    from email_channel.notify import after_approval, after_validation

    record = await receive(build(text=BODY))
    with sync_session() as db:
        complaint = db.get(Complaint, record.complaint_id)
        assert complaint is not None
        after_validation(db, complaint, "needs_review", "Draft that is not approved yet.")
        db.commit()
        after_validation(db, complaint, "needs_review", "Draft that is not approved yet.")
        db.commit()
    async with async_session_factory()() as adb:
        acomplaint = await adb.get(Complaint, record.complaint_id)
        assert acomplaint is not None
        acomplaint.approved_response = "Dear Sara, we are sending a replacement today."
        await after_approval(adb, acomplaint)
        await adb.commit()
        await after_approval(adb, acomplaint)
        await adb.commit()
    with sync_session() as db:
        emails = outbound(db)
        assert [o.kind for o in emails] == ["acknowledgement", "holding", "reply"]
        assert emails[2].body.startswith("Dear Sara, we are sending")
        assert emails[2].in_reply_to == "<m1@example.test>"


async def test_auto_approved_draft_is_sent_as_the_reply(client: httpx.AsyncClient) -> None:
    from email_channel.notify import after_validation

    record = await receive(build(text=BODY))
    with sync_session() as db:
        complaint = db.get(Complaint, record.complaint_id)
        assert complaint is not None
        after_validation(db, complaint, "verified", "Dear Sara, a replacement is on its way.")
        db.commit()
        assert [o.kind for o in outbound(db)] == ["acknowledgement", "reply"]


async def test_non_email_complaints_get_no_email(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    from email_channel.notify import after_validation

    payload = {"title": "Late order", "description": BODY}
    response = await client.post(
        "/api/v1/complaints", headers=auth_headers(Role.CUSTOMER), json=payload
    )
    ref = response.json()["complaint_ref"]
    with sync_session() as db:
        complaint = db.scalar(select(Complaint).where(Complaint.complaint_ref == ref))
        assert complaint is not None
        after_validation(db, complaint, "verified", "Reply text")
        db.commit()
        assert outbound(db) == []


async def test_real_validation_and_review_send_holding_then_reply(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    """End to end through Pipeline 1+2 and the review API, like the chat test."""
    from tests.integration.test_chat_replies import process

    raw = build(text="My charger sparked and smelled burnt when I plugged it in last night.")
    record = await receive(raw)
    with sync_session() as db:
        complaint = db.get(Complaint, record.complaint_id)
        assert complaint is not None
        ref = complaint.complaint_ref
    from tests.fixtures.genai import analysis_json

    process(ref, analysis_json())  # safety: needs review → holding e-mail
    process(ref, analysis_json())  # re-validation must not queue a second holding e-mail
    body = "We are sorry. Please stop using the charger. Our safety team will contact you."
    response = await client.post(
        f"/api/v1/complaints/{ref}/review",
        headers=auth_headers(Role.REVIEWER),
        json={"action": "modify", "response_body": body},
    )
    assert response.status_code == 200, response.text
    with sync_session() as db:
        emails = outbound(db)
        assert [o.kind for o in emails] == ["acknowledgement", "holding", "reply"]
        assert emails[-1].body.startswith(body)
