"""Turning a raw e-mail into what the complaint intake needs."""

from email.header import Header

from email_channel.parsing import (
    clean_subject,
    complaint_ref_in,
    html_to_text,
    order_ref_in,
    parse_email,
    strip_quoted,
)
from tests.emails import build

BODY = "My tablet arrived with a cracked screen and the box was crushed."


def test_plain_message() -> None:
    parsed = parse_email(build(text=BODY))
    assert parsed.from_address == "sara@example.test" and parsed.from_name == "Sara Khan"
    assert parsed.subject == "Broken tablet" and parsed.body == BODY
    assert parsed.message_id == "<m1@example.test>" and not parsed.automated


def test_html_only_becomes_text() -> None:
    parsed = parse_email(build(html="<p>Hello<br>My <b>tablet</b> broke.</p><script>x()</script>"))
    assert parsed.body == "Hello\nMy tablet broke."


def test_encoded_subject_and_name_are_decoded() -> None:
    raw = build(
        sender=f"{Header('Zoë Ölçer', 'utf-8').encode()} <zoe@example.test>",
        subject=Header("Écran cassé 😞", "utf-8").encode(),
        text=BODY,
    )
    parsed = parse_email(raw)
    assert parsed.from_name == "Zoë Ölçer" and parsed.subject == "Écran cassé 😞"


def test_quoted_history_and_signature_are_removed() -> None:
    text = (
        "Still no reply, please help.\n\n-- \nSara\nSent from my phone\n\n"
        "On Mon, 28 Sep 2026 at 10:00, VoltHaven <care@volthaven.test> wrote:\n"
        "> We've received your complaint CMP-000123.\n> Thanks"
    )
    assert strip_quoted(text) == "Still no reply, please help."
    assert strip_quoted("> only quoted\n> lines") == ""
    reply = "Any update?\n\nOn Mon, VoltHaven wrote:\n> Hello Sara,\n> Thank you."
    assert parse_email(build(text=reply)).body == "Any update?"


def test_subject_helpers() -> None:
    assert clean_subject("RE: Fwd: AW: Broken tablet [CMP-000123]") == "Broken tablet"
    assert complaint_ref_in("Re: Broken tablet [CMP-000123]") == "CMP-000123"
    assert complaint_ref_in("no ref here CMP-12") is None
    assert order_ref_in("about order ord-800123 please") == "ORD-800123"


def test_automated_messages_are_flagged() -> None:
    for headers in (
        {"Auto-Submitted": "auto-replied"},
        {"X-Autoreply": "yes"},
        {"Precedence": "bulk"},
        {"List-Id": "<news.example.test>"},
    ):
        assert parse_email(build(text=BODY, headers=headers)).automated
    assert parse_email(build(text=BODY, sender="MAILER-DAEMON@example.test")).automated
    assert not parse_email(build(text=BODY, headers={"Auto-Submitted": "no"})).automated


def test_newsletters_and_service_notifications_are_flagged() -> None:
    # Headers of a real account e-mail from a mailing service (Brevo's "Welcome" message):
    # no Auto-Submitted, Precedence or List-Id, but a one-click unsubscribe link.
    service_mail = {
        "List-Unsubscribe": "<https://r.mailer.example/un/abc>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        "Feedback-ID": "77.32.148.2:14406_-1:14406:Sendinblue",
    }
    assert parse_email(
        build(text=BODY, sender="Brevo <welcome@t.brevo.example>", headers=service_mail)
    ).automated
    for header in ("List-Help", "List-Post", "List-Owner"):
        assert parse_email(build(text=BODY, headers={header: "<mailto:x@example.test>"})).automated
    for sender in ("no-reply@shop.example", "noreply@shop.example", "donotreply@shop.example"):
        assert parse_email(build(text=BODY, sender=sender)).automated
    # A customer's ordinary e-mail is still a complaint.
    assert not parse_email(build(text=BODY, sender="Sara <sara@example.test>")).automated


def test_attachments_and_thread_headers() -> None:
    raw = build(
        text=BODY,
        in_reply_to="<out-1@volthaven.test>",
        attachments=(("photo.png", "image/png", b"\x89PNG\r\n\x1a\n0"),),
    )
    parsed = parse_email(raw)
    assert parsed.in_reply_to == "<out-1@volthaven.test>"
    assert parsed.references == ["<out-1@volthaven.test>"]
    assert [(a.filename, a.content_type) for a in parsed.attachments] == [
        ("photo.png", "image/png")
    ]
    assert parsed.attachments[0].data == b"\x89PNG\r\n\x1a\n0"


def test_missing_message_id_gets_a_stable_one() -> None:
    raw = build(text=BODY, message_id=None)
    assert parse_email(raw).message_id == parse_email(raw).message_id
    assert parse_email(raw).message_id.startswith("<generated-")


def test_html_to_text_keeps_paragraphs() -> None:
    assert html_to_text("<div>One</div><div>Two &amp; three</div>") == "One\nTwo & three"


def test_outlook_and_gmail_quote_styles_are_removed() -> None:
    outlook = "Still broken.\n\n-----Original Message-----\nFrom: VoltHaven\nSent: Monday\nHello"
    assert strip_quoted(outlook) == "Still broken."
    header_block = (
        "Any news?\n\n" + "_" * 32 + "\nFrom: VoltHaven <care@volthaven.test>\n"
        "Sent: Monday, 28 September 2026 10:00\nTo: Sara\nSubject: Re: Broken tablet\n\nHello"
    )
    assert strip_quoted(header_block) == "Any news?"
    bare_from = "Please call me.\n\nFrom: VoltHaven <care@volthaven.test>\nSent: Monday\nTo: Sara"
    assert strip_quoted(bare_from) == "Please call me."
    wrapped = (
        "Thanks.\n\nOn Mon, 28 Sep 2026 at 10:00, VoltHaven <\ncare@volthaven.test> wrote:\n\nHello"
    )
    assert strip_quoted(wrapped) == "Thanks."


def test_quoted_html_blocks_are_removed() -> None:
    html = (
        "<div>New text here.</div>"
        '<div class="gmail_quote">On Mon wrote:<blockquote>Old reply</blockquote></div>'
    )
    assert html_to_text(html) == "New text here."
    assert html_to_text("<p>Top</p><blockquote><p>Quoted</p></blockquote>") == "Top"


def test_unknown_charset_still_gives_readable_text() -> None:
    raw = build(text=BODY).replace(b'charset="utf-8"', b'charset="x-unknown-foo"')
    assert parse_email(raw).body == BODY
