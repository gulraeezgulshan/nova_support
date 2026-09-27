"""Mailbox console: status, lists and processing an e-mail by hand."""

from collections.abc import Callable

import httpx
import pytest

from database.models import Role
from tests.emails import build

pytestmark = pytest.mark.db

BODY = "My tablet arrived with a cracked screen and the box was crushed in transit."
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 40


async def test_status_never_reveals_the_password(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    status = (await client.get("/api/v1/mailbox", headers=auth_headers(Role.AGENT))).json()
    assert status["configured"] is False and "password" not in str(status).lower()
    customer = auth_headers(Role.CUSTOMER)
    assert (await client.get("/api/v1/mailbox", headers=customer)).status_code == 403
    assert (
        await client.post("/api/v1/mailbox/process", headers=customer, data={"body": BODY})
    ).status_code == 403


async def test_process_a_pasted_email(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    agent = auth_headers(Role.AGENT)
    form = {
        "from_address": "Sara@Example.test",
        "from_name": "Sara Khan",
        "subject": "Broken tablet",
        "body": BODY,
    }
    files = [("files", ("photo.png", PNG, "image/png"))]
    result = await client.post("/api/v1/mailbox/process", headers=agent, data=form, files=files)
    assert result.status_code == 201, result.text
    body = result.json()
    assert body["outcome"] == "filed" and body["complaint_ref"].startswith("CMP-")
    assert body["via"] == "manual" and body["from_address"] == "sara@example.test"
    inbound = (await client.get("/api/v1/mailbox/inbound", headers=agent)).json()
    outbound = (await client.get("/api/v1/mailbox/outbound", headers=agent)).json()
    assert [i["outcome"] for i in inbound] == ["filed"]
    assert [o["kind"] for o in outbound] == ["acknowledgement"]
    assert outbound[0]["complaint_ref"] == body["complaint_ref"]
    attachments = await client.get(
        f"/api/v1/complaints/{body['complaint_ref']}/attachments", headers=agent
    )
    assert len(attachments.json()) == 1


async def test_process_an_eml_file(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    raw = build(text=BODY, subject="Re: something")
    result = await client.post(
        "/api/v1/mailbox/process",
        headers=auth_headers(Role.AGENT),
        files={"eml": ("message.eml", raw, "message/rfc822")},
    )
    assert result.status_code == 201 and result.json()["outcome"] == "filed"


@pytest.mark.parametrize(
    "form",
    [{"subject": "x"}, {"from_address": "not-an-address", "body": BODY}],
    ids=["no-sender-or-body", "bad-address"],
)
async def test_process_needs_a_sender_and_body(
    client: httpx.AsyncClient,
    auth_headers: Callable[[Role], dict[str, str]],
    form: dict[str, str],
) -> None:
    result = await client.post(
        "/api/v1/mailbox/process", headers=auth_headers(Role.AGENT), data=form
    )
    assert result.status_code == 422
