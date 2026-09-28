"""IMAP (read) and SMTP or Brevo (send) for the support mailbox, behind small protocols."""

import contextlib
import imaplib
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr
from typing import Protocol

import httpx

from src.core.config import Settings

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
# Threading and loop-prevention headers carried over to Brevo; From/To/Subject go in the body.
BREVO_HEADERS = ("Message-ID", "In-Reply-To", "References", "Auto-Submitted")


class Mailbox(Protocol):
    def unseen(self, limit: int) -> list[tuple[bytes, bytes]]: ...
    def mark_seen(self, uid: bytes) -> None: ...
    def close(self) -> None: ...


class Sender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class ImapMailbox:
    """Reads unseen messages from INBOX without marking them read until asked."""

    def __init__(self, settings: Settings):
        host, user, password = (
            settings.mail_imap_host,
            settings.mail_username,
            settings.mail_password,
        )
        if not (host and user and password):
            raise ValueError("The mailbox is not configured.")
        self._imap = imaplib.IMAP4_SSL(
            host, settings.mail_imap_port, ssl_context=ssl.create_default_context(), timeout=30
        )
        self._imap.login(user, password)
        self._imap.select("INBOX")

    def unseen(self, limit: int) -> list[tuple[bytes, bytes]]:
        _, data = self._imap.uid("search", "UNSEEN")
        uids = (data[0] or b"").split()[:limit]
        messages: list[tuple[bytes, bytes]] = []
        for uid in uids:
            _, parts = self._imap.uid("fetch", uid.decode(), "(BODY.PEEK[])")  # stays unread
            raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
            if isinstance(raw, bytes):
                messages.append((uid, raw))
        return messages

    def mark_seen(self, uid: bytes) -> None:
        self._imap.uid("store", uid.decode(), "+FLAGS", "(\\Seen)")

    def close(self) -> None:
        with contextlib.suppress(imaplib.IMAP4.error, OSError):
            self._imap.logout()


class SmtpSender:
    def __init__(self, settings: Settings):
        self._settings = settings

    def send(self, message: EmailMessage) -> None:
        s = self._settings
        if not (s.mail_smtp_host and s.mail_username and s.mail_password):
            raise ValueError("The mailbox is not configured.")
        context = ssl.create_default_context()
        if s.mail_smtp_port == 465:
            with smtplib.SMTP_SSL(
                s.mail_smtp_host, s.mail_smtp_port, context=context, timeout=30
            ) as smtp:
                smtp.login(s.mail_username, s.mail_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(s.mail_smtp_host, s.mail_smtp_port, timeout=30) as smtp:
                smtp.starttls(context=context)
                smtp.login(s.mail_username, s.mail_password)
                smtp.send_message(message)


class BrevoSender:
    """Sends through Brevo's HTTPS API, for hosts that block outbound SMTP ports.

    Brevo may send from its own domain when the sender is a free-mail address, so Reply-To
    points at the support mailbox: customer replies still arrive where the IMAP check reads.
    """

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self._settings = settings
        self._client = client or httpx.Client(timeout=30)

    def send(self, message: EmailMessage) -> None:
        s = self._settings
        if not (s.brevo_api_key and s.mail_username):
            raise ValueError("Brevo is not configured (BREVO_API_KEY, MAIL_USERNAME).")
        name, _ = parseaddr(str(message["From"]))
        mailbox = {"name": name or s.mail_from_name, "email": s.mail_username}
        body = message.get_body(preferencelist=("plain",))
        payload = {
            "sender": mailbox,
            "replyTo": mailbox,
            "to": [
                {"email": address, **({"name": name} if name else {})}
                for name, address in getaddresses([str(message["To"])])
            ],
            "subject": str(message["Subject"]),
            "textContent": body.get_content() if body else "",
            "headers": {h: str(message[h]) for h in BREVO_HEADERS if message[h]},
        }
        response = self._client.post(
            BREVO_URL,
            json=payload,
            headers={"api-key": s.brevo_api_key, "accept": "application/json"},
        )
        if response.status_code >= 300:
            try:
                reason = response.json().get("message", response.text)
            except ValueError:
                reason = response.text
            raise RuntimeError(f"Brevo refused the e-mail ({response.status_code}): {reason}"[:500])


def get_sender(settings: Settings) -> Sender:
    return BrevoSender(settings) if settings.mail_send_via == "brevo" else SmtpSender(settings)
