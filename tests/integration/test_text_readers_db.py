"""Order e-mails, complaint e-mails and the chat greeting use the saved Customer texts."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select

import app_settings
from database.models import Complaint, OutboundEmail, User
from database.session import async_session_factory, sync_session
from storefront.automation import advance_due_orders
from tests.emails import build
from tests.fixtures.shop import place_order, shopper
from tests.integration.test_email_channel import BODY, receive

pytestmark = pytest.mark.db


def use_texts(orders: dict[str, Any] | None = None, **groups: dict[str, Any]) -> None:
    base = app_settings.defaults()
    changes: dict[str, Any] = {}
    for group, values in groups.items():
        current = getattr(base.texts, group)
        changes[group] = (
            {**current, **values}
            if isinstance(current, dict)
            else current.model_copy(update=values)
        )
    texts = base.texts.model_copy(update=changes)
    update: dict[str, Any] = {"texts": texts}
    if orders:
        update["orders"] = base.orders.model_copy(update=orders)
    app_settings.override(base.model_copy(update=update))


def _emails(kind: str) -> list[OutboundEmail]:
    with sync_session() as db:
        return list(db.scalars(select(OutboundEmail).where(OutboundEmail.kind == kind)))


async def test_order_email_uses_settings(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    shipped = app_settings.defaults().texts.order_emails["shipped"]
    use_texts(
        orders={"delay_chance_pct": 0},
        order_emails={"shipped": shipped.model_copy(update={"subject": "Shipped: {order_ref}"})},
    )
    order = await place_order(client, shopper(create_user, make_token))
    now = datetime.now(UTC) + timedelta(hours=1)
    for _ in range(2):
        advance_due_orders(now)
        now += timedelta(minutes=5)
    [email] = _emails("order_shipped")
    assert email.subject == f"Shipped: {order['order_ref']}"


async def test_acknowledgement_uses_settings(client: httpx.AsyncClient) -> None:
    use_texts(complaint_emails={"acknowledgement": "Hello {name}, logged as {ref} at {shop}."})
    record = await receive(build(text=BODY))
    with sync_session() as db:
        complaint = db.get(Complaint, record.complaint_id)
        assert complaint is not None
        ref = complaint.complaint_ref
    [ack] = _emails("acknowledgement")
    assert ack.body.startswith(f"Hello Sara Khan, logged as {ref} at VoltHaven Electronics.")


async def test_approved_response_gets_signature(client: httpx.AsyncClient) -> None:
    from email_channel.notify import after_approval

    use_texts(complaint_emails={"signature": "Thanks,\n{shop}"})
    record = await receive(build(text=BODY))
    async with async_session_factory()() as adb:
        complaint = await adb.get(Complaint, record.complaint_id)
        assert complaint is not None
        complaint.approved_response = "Dear Sara, we are sending a replacement today."
        await after_approval(adb, complaint)
        await adb.commit()
    [reply] = _emails("reply")
    assert reply.body.endswith("\n\nThanks,\nVoltHaven Electronics")


async def test_greeting_from_settings(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    use_texts(chat={"greeting": "Welcome to {shop}! Which order do you mean?"})
    headers = shopper(create_user, make_token)
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=headers)).json()
    assert (
        conv["messages"][0]["content"]
        == "Welcome to VoltHaven Electronics! Which order do you mean?"
    )
