"""Build raw RFC 5322 messages for tests."""

from email.message import EmailMessage


def build(
    *,
    sender: str = "Sara Khan <sara@example.test>",
    to: str = "care@volthaven.test",
    subject: str = "Broken tablet",
    text: str | None = None,
    html: str | None = None,
    headers: dict[str, str] | None = None,
    attachments: tuple[tuple[str, str, bytes], ...] = (),
    message_id: str | None = "<m1@example.test>",
    in_reply_to: str | None = None,
) -> bytes:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = sender, to, subject
    if message_id:
        msg["Message-ID"] = message_id
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    for key, value in (headers or {}).items():
        msg[key] = value
    if text is not None:
        msg.set_content(text)
    if html is not None:
        if text is None:
            msg.set_content(html, subtype="html")
        else:
            msg.add_alternative(html, subtype="html")
    for filename, content_type, data in attachments:
        maintype, subtype = content_type.split("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return bytes(msg)
