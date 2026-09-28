"""Chat conversation flow over HTTP with a scripted GenAI provider."""

import json
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from database.models import Complaint, Role, User
from database.session import sync_session
from support_chat import service as chat_service
from tests.fixtures.genai import ScriptedProvider

pytestmark = pytest.mark.db

ASKING = json.dumps(
    {
        "reply": "When did it arrive?",
        "title": "Laptop arrived late",
        "missing": ["date"],
        "ready_to_confirm": False,
        "requested_resolution": None,
    }
)
READY = json.dumps(
    {
        "reply": "Thanks, here is what I'll send to our team:",
        "title": "Laptop arrived late",
        "missing": [],
        "ready_to_confirm": True,
        "requested_resolution": "Store credit for the delay",
    }
)


@pytest.fixture
def scripted(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., ScriptedProvider]]:
    def install(*responses: Any) -> ScriptedProvider:
        provider = ScriptedProvider(*responses)
        monkeypatch.setattr(chat_service, "intake_provider", lambda: provider)
        return provider

    yield install


@pytest.fixture
def shopper(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> dict[str, str]:
    user = create_user(Role.CUSTOMER, email="shopper@example.test")
    return {"Authorization": f"Bearer {make_token(user.clerk_user_id)}"}


async def place(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    orders = (
        await client.post(
            "/api/v1/checkout",
            headers=headers,
            json={"lines": [{"sku": "VH-LAP-AB14", "quantity": 1}]},
        )
    ).json()
    return str(orders[0]["order_ref"])


async def test_full_conversation_files_a_complaint_in_the_customers_words(
    client: httpx.AsyncClient, shopper: dict[str, str], scripted: Callable[..., ScriptedProvider]
) -> None:
    order_ref = await place(client, shopper)
    scripted(ASKING, READY)
    conv = (
        await client.post(
            "/api/v1/chat/conversations", json={"order_ref": order_ref}, headers=shopper
        )
    ).json()
    assert conv["order_ref"] == order_ref and conv["messages"][0]["role"] == "assistant"
    base = f"/api/v1/chat/conversations/{conv['id']}"
    first = "My AeroBook laptop arrived a week late and nobody told me why."
    await client.post(f"{base}/messages", json={"text": first}, headers=shopper)
    second = "It came on Monday. I would like store credit for the delay."
    await client.post(f"{base}/messages", json={"text": second}, headers=shopper)
    state = (await client.get(base, headers=shopper)).json()
    assert state["state"] == "confirming"
    summary = state["messages"][-1]
    assert summary["kind"] == "summary" and summary["payload"]["title"] == "Laptop arrived late"

    confirmed = await client.post(f"{base}/confirm", headers=shopper)
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["state"] == "submitted" and body["complaint_ref"].startswith("CMP-")
    assert body["messages"][-1]["kind"] == "reference"
    assert "add photos or documents" in body["messages"][-1]["content"]
    with sync_session() as db:
        complaint = db.scalar(
            select(Complaint).where(Complaint.complaint_ref == body["complaint_ref"])
        )
        assert complaint is not None and complaint.channel == "live_chat"
        assert complaint.description == f"{first}\n{second}"  # the customer's words only
        assert complaint.order is not None and complaint.order.order_ref == order_ref
    assert len(client.app.state.analyses) == 1  # type: ignore[attr-defined]


async def test_second_confirm_is_a_conflict(
    client: httpx.AsyncClient, shopper: dict[str, str], scripted: Callable[..., ScriptedProvider]
) -> None:
    scripted(READY)
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=shopper)).json()
    base = f"/api/v1/chat/conversations/{conv['id']}"
    await client.post(
        f"{base}/messages",
        headers=shopper,
        json={"text": "My charger stopped working after two days, I would like a replacement."},
    )
    assert (await client.post(f"{base}/confirm", headers=shopper)).status_code == 200
    assert (await client.post(f"{base}/confirm", headers=shopper)).status_code == 409


async def test_too_short_description_returns_to_gathering(
    client: httpx.AsyncClient, shopper: dict[str, str], scripted: Callable[..., ScriptedProvider]
) -> None:
    scripted(READY)
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=shopper)).json()
    base = f"/api/v1/chat/conversations/{conv['id']}"
    await client.post(f"{base}/messages", json={"text": "late"}, headers=shopper)
    result = (await client.post(f"{base}/confirm", headers=shopper)).json()
    assert result["state"] == "gathering" and result["complaint_ref"] is None
    assert "more detail" in result["messages"][-1]["content"]


async def test_order_buttons_and_selection(
    client: httpx.AsyncClient, shopper: dict[str, str], scripted: Callable[..., ScriptedProvider]
) -> None:
    order_ref = await place(client, shopper)
    scripted()
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=shopper)).json()
    options = conv["messages"][-1]
    assert options["kind"] == "order_options"
    assert order_ref in [o["order_ref"] for o in options["payload"]["orders"]]
    chosen = (
        await client.post(
            f"/api/v1/chat/conversations/{conv['id']}/order",
            json={"order_ref": order_ref},
            headers=shopper,
        )
    ).json()
    assert chosen["order_ref"] == order_ref and "AeroBook" in chosen["messages"][-1]["content"]


async def test_messages_after_submission_join_the_complaint(
    client: httpx.AsyncClient, shopper: dict[str, str], scripted: Callable[..., ScriptedProvider]
) -> None:
    scripted(READY)
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=shopper)).json()
    base = f"/api/v1/chat/conversations/{conv['id']}"
    await client.post(
        f"{base}/messages",
        headers=shopper,
        json={"text": "My earbuds stopped charging after a week, please replace them."},
    )
    ref = (await client.post(f"{base}/confirm", headers=shopper)).json()["complaint_ref"]
    later = (
        await client.post(
            f"{base}/messages", headers=shopper, json={"text": "The case is also cracked now."}
        )
    ).json()
    assert later["messages"][-1]["kind"] == "acknowledgement"
    detail = (await client.get(f"/api/v1/complaints/{ref}", headers=shopper)).json()
    assert any("case is also cracked" in e["message"] for e in detail["events"])


async def test_access_is_limited_to_the_customer(
    client: httpx.AsyncClient,
    shopper: dict[str, str],
    auth_headers: Callable[[Role], dict[str, str]],
    scripted: Callable[..., ScriptedProvider],
) -> None:
    order_ref = await place(client, shopper)
    scripted()
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=shopper)).json()
    other = auth_headers(Role.CUSTOMER)
    assert (
        await client.get(f"/api/v1/chat/conversations/{conv['id']}", headers=other)
    ).status_code == 404
    started = await client.post(
        "/api/v1/chat/conversations", json={"order_ref": order_ref}, headers=other
    )
    assert started.status_code == 404
    assert (await client.post("/api/v1/chat/conversations", json={})).status_code == 401


async def test_limits(
    client: httpx.AsyncClient, shopper: dict[str, str], scripted: Callable[..., ScriptedProvider]
) -> None:
    scripted(*[ASKING] * 40)
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=shopper)).json()
    base = f"/api/v1/chat/conversations/{conv['id']}"
    too_long = await client.post(f"{base}/messages", json={"text": "x" * 2001}, headers=shopper)
    assert too_long.status_code == 422
    for i in range(30):
        await client.post(f"{base}/messages", json={"text": f"detail {i}"}, headers=shopper)
    capped = await client.post(f"{base}/messages", json={"text": "one more"}, headers=shopper)
    assert capped.status_code == 422


async def test_each_turn_sees_the_assistants_earlier_questions(
    client: httpx.AsyncClient, shopper: dict[str, str], scripted: Callable[..., ScriptedProvider]
) -> None:
    provider = scripted(ASKING, READY)
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=shopper)).json()
    base = f"/api/v1/chat/conversations/{conv['id']}"
    await client.post(
        f"{base}/messages", headers=shopper, json={"text": "How long do refunds take?"}
    )
    await client.post(f"{base}/messages", headers=shopper, json={"text": "It's a general question"})
    second_turn = provider.requests[1].user
    assert "Assistant: When did it arrive?" in second_turn  # the question it asked last turn
    assert (
        second_turn.index("How long do refunds take?")
        < second_turn.index("Assistant: When did it arrive?")
        < second_turn.index("It's a general question")
    )
