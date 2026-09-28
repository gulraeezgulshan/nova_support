"""The e-mail and chat hooks send a holding message instead of the reply when told to."""

import json
from collections.abc import Callable

import httpx
import pytest
from sqlalchemy import select

from database.models import ChatMessage, Complaint, InboundEmail, OutboundEmail, Role, User
from database.session import async_session_factory, sync_session
from email_channel.inbound import process_email
from email_channel.parsing import parse_email
from src.core.storage import get_storage
from support_chat import service as chat_service
from tests.emails import build
from tests.fixtures.genai import ScriptedProvider

pytestmark = pytest.mark.db
BODY = "My tablet arrived with a cracked screen and the box was crushed in transit."
READY = json.dumps(
    {
        "reply": "Here is the summary:",
        "title": "Promotion code not applied",
        "missing": [],
        "ready_to_confirm": True,
        "requested_resolution": None,
    }
)


async def receive(raw: bytes) -> InboundEmail:
    async with async_session_factory()() as db:
        return await process_email(
            db, parse_email(raw), via="manual", own_address="care@volthaven.test",
            storage=get_storage(),
        )  # fmt: skip


async def test_email_hook_holds_the_reply(client: httpx.AsyncClient) -> None:
    from email_channel.notify import after_validation

    record = await receive(build(text=BODY))
    with sync_session() as db:
        complaint = db.get(Complaint, record.complaint_id)
        assert complaint is not None
        after_validation(db, complaint, "verified", "Dear Sara, a replacement.", auto_reply=False)
        db.commit()
        kinds = [
            o.kind for o in db.scalars(select(OutboundEmail).order_by(OutboundEmail.created_at))
        ]
    assert kinds == ["acknowledgement", "holding"]


async def test_chat_hook_holds_the_reply(
    client: httpx.AsyncClient,
    create_user: Callable[..., User],
    make_token: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from support_chat import notify

    user = create_user(Role.CUSTOMER)
    headers = {"Authorization": f"Bearer {make_token(user.clerk_user_id)}"}
    monkeypatch.setattr(chat_service, "intake_provider", lambda: ScriptedProvider(READY))
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=headers)).json()
    base = f"/api/v1/chat/conversations/{conv['id']}"
    text = "The promotion code SAVE10 was not applied to my order at checkout."
    await client.post(f"{base}/messages", json={"text": text}, headers=headers)
    ref = (await client.post(f"{base}/confirm", headers=headers)).json()["complaint_ref"]
    with sync_session() as db:
        complaint = db.scalar(select(Complaint).where(Complaint.complaint_ref == ref))
        assert complaint is not None
        notify.after_validation(
            db, complaint, "verified", "We checked your order.", auto_reply=False
        )
        db.commit()
        kinds = list(db.scalars(select(ChatMessage.kind)))
    assert "reply" not in kinds and kinds.count("holding") == 1
