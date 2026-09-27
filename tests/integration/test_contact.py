"""Contact us routing, the enquiries inbox and newsletter sign-ups."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select

from database.models import AuditEvent, Complaint, Enquiry, NewsletterSubscriber, Role, User
from database.session import sync_session

pytestmark = pytest.mark.db

CARD = "4111 1111 1111 1111"


def form(**overrides: Any) -> dict[str, Any]:
    return {
        "name": "Sara Khan",
        "email": "sara@example.test",
        "topic": "product_question",
        "message": "Does the AeroBook 14 support two external monitors at once?",
        **overrides,
    }


@pytest.fixture
def signed_in(create_user: Callable[..., User], make_token: Callable[..., str]) -> dict[str, str]:
    user = create_user(Role.CUSTOMER, email="sara@example.test")
    return {"Authorization": f"Bearer {make_token(user.clerk_user_id)}"}


async def buy(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    body = {"lines": [{"sku": "VH-TAB-T11", "quantity": 1}]}
    response = await client.post("/api/v1/checkout", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return str(response.json()[0]["order_ref"])


async def test_questions_become_redacted_enquiries(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/contact", json=form(message=f"My card {CARD} was declined, why?")
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "enquiry" and body["reference"] == "ENQ-000001"
    with sync_session() as db:
        enquiry = db.scalar(select(Enquiry))
        assert enquiry is not None and enquiry.user_id is None
        assert CARD not in enquiry.message and "[card ending 1111]" in enquiry.message
        assert db.scalar(select(func.count()).select_from(Complaint)) == 0


async def test_order_problems_need_sign_in(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/contact", json=form(topic="order_problem"))
    assert response.status_code == 401
    assert "sign in" in response.json()["detail"].lower()


async def test_order_problems_become_web_form_complaints(
    client: httpx.AsyncClient, signed_in: dict[str, str]
) -> None:
    order_ref = await buy(client, signed_in)
    body = form(
        topic="order_problem",
        order_ref=order_ref,
        message="My tablet arrived with a cracked screen and the box was crushed.",
    )
    response = await client.post("/api/v1/contact", json=body, headers=signed_in)
    assert response.status_code == 201, response.text
    assert response.json()["kind"] == "complaint"
    assert response.json()["reference"].startswith("CMP-")
    with sync_session() as db:
        complaint = db.scalar(select(Complaint))
        assert complaint is not None and complaint.channel == "web_form"
        assert complaint.order is not None and complaint.order.order_ref == order_ref
    assert len(client.app.state.analyses) == 1  # type: ignore[attr-defined]
    again = await client.post("/api/v1/contact", json=body, headers=signed_in)
    assert again.status_code == 409  # a double submit is caught by the duplicate check


async def test_someone_elses_order_is_rejected(
    client: httpx.AsyncClient,
    signed_in: dict[str, str],
    auth_headers: Callable[[Role], dict[str, str]],
) -> None:
    order_ref = await buy(client, auth_headers(Role.CUSTOMER))
    body = form(
        topic="order_problem",
        order_ref=order_ref,
        message="This order arrived broken and I would like a replacement please.",
    )
    response = await client.post("/api/v1/contact", headers=signed_in, json=body)
    assert response.status_code == 422


async def test_honeypot_is_dropped_silently(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/contact", json=form(website="http://spam.example"))
    assert response.status_code == 201 and response.json() == {"kind": "ignored", "reference": None}
    with sync_session() as db:
        assert db.scalar(select(func.count()).select_from(Enquiry)) == 0


async def test_invalid_contact_forms_are_rejected(client: httpx.AsyncClient) -> None:
    for bad in [form(email="not-an-email"), form(topic="sales"), form(message="hi")]:
        assert (await client.post("/api/v1/contact", json=bad)).status_code == 422


async def test_enquiry_inbox_is_for_staff(
    client: httpx.AsyncClient,
    signed_in: dict[str, str],
    auth_headers: Callable[[Role], dict[str, str]],
) -> None:
    ref = (await client.post("/api/v1/contact", json=form(), headers=signed_in)).json()["reference"]
    assert (await client.get("/api/v1/enquiries", headers=signed_in)).status_code == 403
    agent = auth_headers(Role.AGENT)
    listed = (await client.get("/api/v1/enquiries", headers=agent, params={"status": "new"})).json()
    assert [e["ref"] for e in listed] == [ref]
    assert listed[0]["can_convert"] is True

    handled = await client.patch(
        f"/api/v1/enquiries/{ref}", headers=agent, json={"status": "handled"}
    )
    assert handled.status_code == 200 and handled.json()["status"] == "handled"
    assert (
        await client.get("/api/v1/enquiries", headers=agent, params={"status": "new"})
    ).json() == []

    converted = await client.post(f"/api/v1/enquiries/{ref}/convert", headers=agent)
    assert converted.status_code == 200, converted.text
    assert converted.json()["complaint_ref"].startswith("CMP-")
    again = await client.post(f"/api/v1/enquiries/{ref}/convert", headers=agent)
    assert again.status_code == 422  # only once
    missing = await client.patch(
        "/api/v1/enquiries/ENQ-999999", headers=agent, json={"status": "new"}
    )
    assert missing.status_code == 404
    with sync_session() as db:
        actions = set(
            db.scalars(select(AuditEvent.action).where(AuditEvent.entity_type == "enquiry"))
        )
        assert {"enquiry.received", "enquiry.status_changed", "enquiry.converted"} <= actions


async def test_anonymous_enquiries_cannot_be_converted(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    ref = (await client.post("/api/v1/contact", json=form())).json()["reference"]
    agent = auth_headers(Role.AGENT)
    assert (await client.get("/api/v1/enquiries", headers=agent)).json()[0]["can_convert"] is False
    response = await client.post(f"/api/v1/enquiries/{ref}/convert", headers=agent)
    assert response.status_code == 422


async def test_newsletter_is_idempotent(client: httpx.AsyncClient) -> None:
    for _ in range(2):
        response = await client.post(
            "/api/v1/newsletter", json={"email": "Fan@Example.test", "source": "footer"}
        )
        assert response.status_code == 204
    assert (await client.post("/api/v1/newsletter", json={"email": "nope"})).status_code == 422
    with sync_session() as db:
        assert list(db.scalars(select(NewsletterSubscriber.email))) == ["fan@example.test"]


async def test_complaint_titles_never_keep_part_of_a_card_number(
    client: httpx.AsyncClient, signed_in: dict[str, str]
) -> None:
    message = (
        f"Charged twice on my order last Friday, the card used was {CARD} and I "
        "would like the second payment refunded please."
    )
    response = await client.post(
        "/api/v1/contact", headers=signed_in, json=form(topic="order_problem", message=message)
    )
    assert response.status_code == 201, response.text
    with sync_session() as db:
        complaint = db.scalar(select(Complaint))
        assert complaint is not None
        assert "4111" not in complaint.title and "1111 111" not in complaint.title
        assert CARD not in complaint.description


async def test_a_short_first_line_still_files_the_complaint(
    client: httpx.AsyncClient, signed_in: dict[str, str]
) -> None:
    message = "Hi\nMy tablet arrived with a cracked screen and the box was crushed."
    response = await client.post(
        "/api/v1/contact", headers=signed_in, json=form(topic="order_problem", message=message)
    )
    assert response.status_code == 201, response.text
    with sync_session() as db:
        complaint = db.scalar(select(Complaint))
        assert complaint is not None and complaint.title.startswith("Hi My tablet arrived")
