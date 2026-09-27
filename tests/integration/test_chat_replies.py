"""Validated replies and holding messages reach the chat, once."""

import json
from collections.abc import Callable

import httpx
import pytest
from sqlalchemy import select

from database.models import Complaint, Role, User
from database.session import sync_session
from genai_pipeline.pipeline import run_analysis
from knowledge_base.embeddings import get_embedder
from python_validation.pipeline import run_validation
from src.core.config import get_settings
from support_chat import service as chat_service
from tests.fixtures.genai import ScriptedProvider, analysis_json

pytestmark = pytest.mark.db

READY = json.dumps(
    {
        "reply": "Here is the summary:",
        "title": "Charger stopped working",
        "missing": [],
        "ready_to_confirm": True,
        "requested_resolution": None,
    }
)


async def submitted(
    client: httpx.AsyncClient, headers: dict[str, str], text: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, str]:
    monkeypatch.setattr(chat_service, "intake_provider", lambda: ScriptedProvider(READY))
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=headers)).json()
    base = f"/api/v1/chat/conversations/{conv['id']}"
    await client.post(f"{base}/messages", json={"text": text}, headers=headers)
    body = (await client.post(f"{base}/confirm", headers=headers)).json()
    return base, body["complaint_ref"]


def process(ref: str, answer: str) -> None:
    with sync_session() as db:
        complaint = db.scalar(select(Complaint).where(Complaint.complaint_ref == ref))
        assert complaint is not None
        run_analysis(
            db,
            complaint.id,
            provider=ScriptedProvider(answer),
            embedder=get_embedder(),
            settings=get_settings(),
        )
    with sync_session() as db:
        complaint = db.scalar(select(Complaint).where(Complaint.complaint_ref == ref))
        assert complaint is not None
        run_validation(db, complaint.id)


@pytest.fixture
def customer(create_user: Callable[..., User], make_token: Callable[..., str]) -> dict[str, str]:
    user = create_user(Role.CUSTOMER)
    return {"Authorization": f"Bearer {make_token(user.clerk_user_id)}"}


async def test_needs_review_posts_holding_then_the_approved_reply(
    client: httpx.AsyncClient,
    customer: dict[str, str],
    auth_headers: Callable[[Role], dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, ref = await submitted(
        client,
        customer,
        "My charger sparked and smelled burnt when I plugged it in last night.",
        monkeypatch,
    )
    process(ref, analysis_json())  # safety complaint: level 5, always needs review
    process(ref, analysis_json())  # re-validation must not post a second holding message
    messages = (await client.get(f"{base}/messages", headers=customer)).json()
    assert [m["kind"] for m in messages].count("holding") == 1
    body = "We are sorry. Please stop using the charger. Our safety team will contact you."
    reviewer = auth_headers(Role.REVIEWER)
    await client.post(
        f"/api/v1/complaints/{ref}/review",
        headers=reviewer,
        json={"action": "modify", "response_body": body},
    )
    messages = (await client.get(f"{base}/messages", headers=customer)).json()
    assert messages[-1]["kind"] == "reply" and messages[-1]["content"] == body


async def test_verified_reply_is_posted_automatically(
    client: httpx.AsyncClient,
    customer: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, ref = await submitted(
        client,
        customer,
        "The promotion code SAVE10 was not applied to my order at checkout.",
        monkeypatch,
    )
    from support_chat import notify

    with sync_session() as db:
        complaint = db.scalar(select(Complaint).where(Complaint.complaint_ref == ref))
        assert complaint is not None
        notify.after_validation(db, complaint, "verified", "We have checked your order.")
        notify.after_validation(db, complaint, "verified", "We have checked your order.")
        db.commit()
    messages = (await client.get(f"{base}/messages", headers=customer)).json()
    replies = [m for m in messages if m["kind"] == "reply"]
    assert [r["content"] for r in replies] == ["We have checked your order."]
