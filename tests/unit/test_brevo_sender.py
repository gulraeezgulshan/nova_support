"""Sending through Brevo's HTTPS API (for hosts that block outbound SMTP, e.g. Railway)."""

import json
from email.message import EmailMessage

import httpx
import pytest

from email_channel.transport import BrevoSender, SmtpSender, get_sender
from src.core.config import Settings, get_settings

KEY = "xkeysib-test-key"


def settings(**update: object) -> Settings:
    base = {
        "mail_imap_host": "imap.test",
        "mail_smtp_host": None,
        "mail_username": "care@volthaven.test",
        "mail_password": "app-password",
        "mail_from_name": "VoltHaven Customer Care",
        "mail_send_via": "brevo",
        "brevo_api_key": KEY,
    }
    return get_settings().model_copy(update={**base, **update})


def message() -> EmailMessage:
    m = EmailMessage()
    m["From"] = "VoltHaven Customer Care <care@volthaven.test>"
    m["To"] = "Sara Khan <sara@example.test>"
    m["Subject"] = "Re: Cracked screen [CMP-000643]"
    m["Message-ID"] = "<reply-1@volthaven.test>"
    m["In-Reply-To"] = "<original@example.test>"
    m["References"] = "<original@example.test>"
    m["Auto-Submitted"] = "no"
    m.set_content("Hello Sara,\n\nWe are sending a replacement.\n")
    return m


def capture(
    status: int = 201, body: object | None = None
) -> tuple[list[httpx.Request], httpx.Client]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, json=body if body is not None else {"messageId": "<x@brevo>"})

    return requests, httpx.Client(transport=httpx.MockTransport(handler))


def test_brevo_sends_the_message_as_json_with_reply_to_the_support_mailbox() -> None:
    requests, client = capture()
    BrevoSender(settings(), client=client).send(message())

    [request] = requests
    assert request.method == "POST"
    assert str(request.url) == "https://api.brevo.com/v3/smtp/email"
    assert request.headers["api-key"] == KEY
    payload = json.loads(request.content)
    assert payload["sender"] == {"name": "VoltHaven Customer Care", "email": "care@volthaven.test"}
    assert payload["to"] == [{"email": "sara@example.test", "name": "Sara Khan"}]
    # Customer replies must come back to the mailbox SupportNova reads, whatever Brevo sends from.
    assert payload["replyTo"] == {"email": "care@volthaven.test", "name": "VoltHaven Customer Care"}
    assert payload["subject"] == "Re: Cracked screen [CMP-000643]"
    assert payload["textContent"] == "Hello Sara,\n\nWe are sending a replacement.\n"
    assert payload["headers"] == {
        "Message-ID": "<reply-1@volthaven.test>",
        "In-Reply-To": "<original@example.test>",
        "References": "<original@example.test>",
        "Auto-Submitted": "no",
    }


def test_brevo_error_is_raised_with_its_reason_but_never_the_key() -> None:
    _, client = capture(400, {"code": "invalid_parameter", "message": "sender is not valid"})
    with pytest.raises(RuntimeError) as exc:
        BrevoSender(settings(), client=client).send(message())
    assert "400" in str(exc.value) and "sender is not valid" in str(exc.value)
    assert KEY not in str(exc.value)


def test_brevo_without_a_key_refuses_to_send() -> None:
    _, client = capture()
    with pytest.raises(ValueError):
        BrevoSender(settings(brevo_api_key=None), client=client).send(message())


def test_sender_is_chosen_by_setting() -> None:
    assert isinstance(get_sender(settings()), BrevoSender)
    assert isinstance(get_sender(settings(mail_send_via="smtp")), SmtpSender)


def test_brevo_mailbox_needs_the_key_but_not_an_smtp_host() -> None:
    assert settings().mailbox_configured
    assert not settings(brevo_api_key=None).mailbox_configured
    assert not settings(mail_send_via="smtp").mailbox_configured  # SMTP still needs its host
