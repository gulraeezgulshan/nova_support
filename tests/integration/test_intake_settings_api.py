"""Duplicate, attachment and chat limits from the run-time settings, end to end."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest

import app_settings
from complaint_processing.service import ComplaintInput, submit_complaint
from database.models import Customer, CustomerType, Role, User
from database.session import async_session_factory
from tests.fixtures.genai import ScriptedProvider
from tests.integration.test_attachments_api import PNG, attach, file_complaint
from tests.integration.test_chat_api import ASKING, place

pytestmark = pytest.mark.db


def use_intake(**changes: Any) -> None:
    base = app_settings.defaults()
    app_settings.override(
        base.model_copy(update={"intake": base.intake.model_copy(update=changes)})
    )


@pytest.fixture
def owner(create_user: Callable[..., User], make_token: Callable[..., str]) -> dict[str, str]:
    user = create_user(Role.CUSTOMER, email="owner@example.test")
    return {"Authorization": f"Bearer {make_token(user.clerk_user_id)}"}


async def _pair(text: str, resend: str) -> tuple[Any, Any]:
    async with async_session_factory()() as db:
        customer = Customer(
            customer_ref="CUST-900021", full_name="Ann", customer_type=CustomerType.STANDARD
        )
        db.add(customer)
        await db.flush()
        first = await submit_complaint(
            db,
            customer=customer,
            submitted_by=None,
            enqueue=False,
            data=ComplaintInput(title="Headphones broken", description=text),
        )
        second = await submit_complaint(
            db,
            customer=customer,
            submitted_by=None,
            enqueue=False,
            data=ComplaintInput(title="Headphones broken again", description=resend),
        )
    return first, second


TEXT = "My headphones stopped charging after two weeks and the right earbud is silent."
RESEND = "My headphones stopped charging after two weeks and the left earbud is silent."


async def test_near_duplicate_linked_by_default(clean_db: None) -> None:
    first, second = await _pair(TEXT, RESEND)
    assert second.duplicate_of_id == first.id


async def test_near_duplicate_ratio_from_settings(clean_db: None) -> None:
    use_intake(near_duplicate_min_ratio=100, related_min_similarity=0.99)
    _, second = await _pair(TEXT, RESEND)
    assert second.duplicate_of_id is None


async def test_attachment_count_from_settings(
    client: httpx.AsyncClient, owner: dict[str, str]
) -> None:
    use_intake(max_attachments=1)
    ref = await file_complaint(client, owner)
    assert (await attach(client, ref, owner, "one.png", PNG)).status_code == 201
    second = await attach(client, ref, owner, "two.png", PNG)
    assert second.status_code == 422
    assert second.json()["detail"] == "A complaint can have at most 1 attachments."


async def test_attachment_size_from_settings(
    client: httpx.AsyncClient, owner: dict[str, str]
) -> None:
    use_intake(max_attachment_mb=1)
    ref = await file_complaint(client, owner)
    big = PNG + b"0" * (1024 * 1024 + 512 * 1024)
    response = await attach(client, ref, owner, "big.png", big)
    assert response.status_code == 422
    assert response.json()["detail"] == "Files must be 1 MB or smaller."


async def test_chat_message_length_from_settings(
    client: httpx.AsyncClient,
    owner: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from support_chat import service as chat_service

    monkeypatch.setattr(chat_service, "intake_provider", lambda: ScriptedProvider(ASKING))
    use_intake(chat_max_message_chars=200)
    order_ref = await place(client, owner)
    conv = (
        await client.post(
            "/api/v1/chat/conversations", json={"order_ref": order_ref}, headers=owner
        )
    ).json()
    r = await client.post(
        f"/api/v1/chat/conversations/{conv['id']}/messages", json={"text": "x" * 300}, headers=owner
    )
    assert r.status_code == 422
    assert r.json()["detail"] == "Messages are limited to 200 characters."
