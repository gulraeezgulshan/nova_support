import base64
import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from svix.webhooks import Webhook

from src.core.config import Settings, get_settings

pytestmark = pytest.mark.db

SECRET = "whsec_" + base64.b64encode(b"test-webhook-secret-32-bytes-long").decode()


def signed_request(event: dict[str, Any], secret: str = SECRET) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(event).encode()
    msg_id, timestamp = "msg_test", datetime.now(UTC)
    signature = Webhook(secret).sign(msg_id, timestamp, body.decode())
    headers = {
        "svix-id": msg_id,
        "svix-timestamp": str(int(timestamp.timestamp())),
        "svix-signature": signature,
        "content-type": "application/json",
    }
    return body, headers


def user_event(event_type: str, email: str = "new@example.test") -> dict[str, Any]:
    return {
        "type": event_type,
        "data": {
            "id": "user_webhook",
            "first_name": "Web",
            "last_name": "Hook",
            "primary_email_address_id": "idn_1",
            "email_addresses": [{"id": "idn_1", "email_address": email}],
        },
    }


@pytest.fixture
def webhook_client(client: httpx.AsyncClient) -> httpx.AsyncClient:
    client.app.dependency_overrides[get_settings] = lambda: Settings(  # type: ignore[attr-defined]
        clerk_webhook_signing_secret=SECRET
    )
    return client


async def test_user_created_and_deleted_events_sync_local_user(
    webhook_client: httpx.AsyncClient, make_token: Any
) -> None:
    body, headers = signed_request(user_event("user.created"))
    response = await webhook_client.post("/api/v1/webhooks/clerk", content=body, headers=headers)
    assert response.status_code == 204

    token = make_token("user_webhook")
    me = await webhook_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert (me.json()["email"], me.json()["full_name"]) == ("new@example.test", "Web Hook")

    body, headers = signed_request(user_event("user.deleted"))
    await webhook_client.post("/api/v1/webhooks/clerk", content=body, headers=headers)
    me = await webhook_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 403


async def test_forged_signature_is_rejected(webhook_client: httpx.AsyncClient) -> None:
    forged_secret = "whsec_" + base64.b64encode(b"attacker-secret-attacker-secret!").decode()
    body, headers = signed_request(user_event("user.created"), secret=forged_secret)
    response = await webhook_client.post("/api/v1/webhooks/clerk", content=body, headers=headers)
    assert response.status_code == 400
