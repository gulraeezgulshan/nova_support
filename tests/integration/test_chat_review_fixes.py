"""Regressions for the final review of the support chat."""

import asyncio
import json
from collections.abc import Callable

import httpx
import pytest
from sqlalchemy import func, select

from complaint_processing import service as complaint_service
from database.models import ChatConversation, Complaint, Role, User
from database.session import sync_session
from support_chat import notify
from support_chat import service as chat_service
from tests.fixtures.genai import ScriptedProvider

pytestmark = pytest.mark.db

READY = json.dumps(
    {
        "reply": "Here is the summary:",
        "title": "Earbuds stopped charging",
        "missing": [],
        "ready_to_confirm": True,
        "requested_resolution": None,
    }
)
TEXT = "My earbuds stopped charging after a week of normal use, please replace them."


@pytest.fixture
def customer(create_user: Callable[..., User], make_token: Callable[..., str]) -> dict[str, str]:
    user = create_user(Role.CUSTOMER)
    return {"Authorization": f"Bearer {make_token(user.clerk_user_id)}"}


async def ready_conversation(
    client: httpx.AsyncClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> str:
    monkeypatch.setattr(chat_service, "intake_provider", lambda: ScriptedProvider(READY))
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=headers)).json()
    base = f"/api/v1/chat/conversations/{conv['id']}"
    await client.post(f"{base}/messages", json={"text": TEXT}, headers=headers)
    return base


async def test_analysis_is_queued_only_after_the_chat_is_linked(
    client: httpx.AsyncClient, customer: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    linked: list[bool] = []

    def enqueue(complaint_id: object, _by: object = None) -> None:
        with sync_session() as db:
            linked.append(
                bool(
                    db.scalar(
                        select(ChatConversation.id).where(
                            ChatConversation.complaint_id == complaint_id
                        )
                    )
                )
            )

    monkeypatch.setattr(complaint_service, "enqueue_analysis", enqueue)
    base = await ready_conversation(client, customer, monkeypatch)
    assert (await client.post(f"{base}/confirm", headers=customer)).status_code == 200
    assert linked == [True]


async def test_concurrent_confirms_create_one_complaint(
    client: httpx.AsyncClient, customer: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    base = await ready_conversation(client, customer, monkeypatch)
    first, second = await asyncio.gather(
        client.post(f"{base}/confirm", headers=customer),
        client.post(f"{base}/confirm", headers=customer),
    )
    assert sorted([first.status_code, second.status_code]) == [200, 409]
    with sync_session() as db:
        assert db.scalar(select(func.count()).select_from(Complaint)) == 1


async def test_a_reviewer_reply_is_not_followed_by_the_old_draft(
    client: httpx.AsyncClient,
    customer: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: Callable[[Role], dict[str, str]],
) -> None:
    base = await ready_conversation(client, customer, monkeypatch)
    ref = (await client.post(f"{base}/confirm", headers=customer)).json()["complaint_ref"]
    await client.post(
        f"/api/v1/complaints/{ref}/review",
        headers=auth_headers(Role.REVIEWER),
        json={"action": "modify", "response_body": "Approved text."},
    )
    with sync_session() as db:
        complaint = db.scalar(select(Complaint).where(Complaint.complaint_ref == ref))
        assert complaint is not None
        notify.after_validation(db, complaint, "verified", "Old unreviewed draft.")
        notify.after_validation(db, complaint, "needs_review", None)
        db.commit()
    messages = (await client.get(f"{base}/messages", headers=customer)).json()
    assert [m["content"] for m in messages if m["kind"] == "reply"] == ["Approved text."]
    assert not any(m["kind"] == "holding" for m in messages)


async def test_reopening_the_chat_after_filing_starts_fresh_and_links_back(
    client: httpx.AsyncClient, customer: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    base = await ready_conversation(client, customer, monkeypatch)
    submitted = (await client.post(f"{base}/confirm", headers=customer)).json()
    again = (await client.post("/api/v1/chat/conversations", json={}, headers=customer)).json()
    assert again["id"] != submitted["id"] and again["complaint_ref"] is None
    assert again["recent_complaint_ref"] == submitted["complaint_ref"]
    fresh = (
        await client.post("/api/v1/chat/conversations", json={"new": True}, headers=customer)
    ).json()
    assert fresh["id"] != submitted["id"] and fresh["state"] == "gathering"


async def test_a_stuck_conversation_can_be_restarted(
    client: httpx.AsyncClient, customer: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    base = await ready_conversation(client, customer, monkeypatch)
    old_id = base.rsplit("/", 1)[1]
    fresh = (
        await client.post("/api/v1/chat/conversations", json={"new": True}, headers=customer)
    ).json()
    assert fresh["id"] != old_id
    with sync_session() as db:
        old = db.get(ChatConversation, old_id)
        assert old is not None and old.state == "closed"


async def test_messages_cannot_exceed_the_complaint_length(
    client: httpx.AsyncClient, customer: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(chat_service, "intake_provider", lambda: None)
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=customer)).json()
    base = f"/api/v1/chat/conversations/{conv['id']}"
    for _ in range(2):
        ok = await client.post(f"{base}/messages", json={"text": "x " * 999}, headers=customer)
        assert ok.status_code == 200
    too_much = await client.post(f"{base}/messages", json={"text": "y " * 999}, headers=customer)
    assert too_much.status_code == 422 and "too long" in too_much.json()["detail"]


async def test_customers_do_not_see_internal_ai_details(
    client: httpx.AsyncClient,
    customer: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: Callable[[Role], dict[str, str]],
) -> None:
    base = await ready_conversation(client, customer, monkeypatch)
    messages = (await client.get(f"{base}/messages", headers=customer)).json()
    assert all("intake" not in m["payload"] for m in messages)
    ref = (await client.post(f"{base}/confirm", headers=customer)).json()["complaint_ref"]
    staff = (
        await client.get(f"/api/v1/complaints/{ref}/chat", headers=auth_headers(Role.AGENT))
    ).json()
    assert any("intake" in m["payload"] for m in staff)
