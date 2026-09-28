"""Raw e-mail → sender, subject, readable body, thread headers and attachments."""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from html.parser import HTMLParser

PREFIX = re.compile(r"^\s*((re|fw|fwd|aw|sv|antw)\s*:\s*)+", re.IGNORECASE)
REF_TAG = re.compile(r"\[(CMP-\d{6})\]", re.IGNORECASE)
ORDER_REF = re.compile(r"\bORD-\d{6}\b", re.IGNORECASE)
WROTE = re.compile(r"^On .{0,300}wrote:\s*$", re.IGNORECASE)
ORIGINAL = re.compile(r"^-{2,}\s*(Original Message|Forwarded message)\s*-{2,}$", re.IGNORECASE)
UNDERSCORES = re.compile(r"^_{20,}$")
AUTOMATED_SENDERS = (
    "mailer-daemon",
    "postmaster",
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
)


@dataclass
class ParsedAttachment:
    filename: str
    content_type: str
    data: bytes


@dataclass
class ParsedEmail:
    message_id: str
    from_address: str
    from_name: str | None
    subject: str
    body: str
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    attachments: list[ParsedAttachment] = field(default_factory=list)
    automated: bool = False
    date: datetime | None = None


HTML_BLOCKS = frozenset({"p", "div", "li", "tr", "h1", "h2", "h3", "h4"})
VOID_TAGS = frozenset({"br", "img", "hr", "meta", "link", "input", "wbr", "col", "area", "base"})


class _Text(HTMLParser):
    """HTML → text; scripts, styles and quoted history (blockquote, .gmail_quote) dropped."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[bool] = []  # per open element: is it (inside) a skipped subtree?

    def _skipping(self) -> bool:
        return bool(self.stack) and self.stack[-1]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = " ".join(v or "" for k, v in attrs if k == "class")
        skipped = tag in {"script", "style", "blockquote"} or "gmail_quote" in classes
        if tag in VOID_TAGS:
            if tag == "br" and not self._skipping():
                self.parts.append("\n")
            return
        self.stack.append(self._skipping() or skipped)
        if tag in HTML_BLOCKS and not self._skipping():
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS:
            return
        if self.stack:
            self.stack.pop()
        if tag in HTML_BLOCKS and not self._skipping():
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skipping():
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line)


def _history_starts(lines: list[str], i: int) -> bool:
    """Does quoted history (Gmail, Apple Mail, Outlook) start at line i?"""
    line = lines[i].strip()
    following = [s.strip() for s in lines[i + 1 : i + 5]]
    if WROTE.match(line) or ORIGINAL.match(line):
        return True
    if line.startswith("On ") and following and following[0].endswith("wrote:"):
        return True  # attribution wrapped over two lines
    if UNDERSCORES.match(line) and any(s.startswith("From:") for s in following[:2]):
        return True
    return line.startswith("From:") and any(s.startswith(("Sent:", "Date:")) for s in following)


def strip_quoted(text: str) -> str:
    """Drop quoted history ('>' lines, 'On … wrote:', Outlook headers) and the signature."""
    lines = text.replace("\r\n", "\n").split("\n")
    kept: list[str] = []
    for i, line in enumerate(lines):
        if _history_starts(lines, i) or line.rstrip() == "--" or line.startswith("-- "):
            break
        if line.lstrip().startswith(">"):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def clean_subject(subject: str) -> str:
    """'RE: Fwd: Broken tablet [CMP-000123]' → 'Broken tablet'."""
    return " ".join(REF_TAG.sub("", PREFIX.sub("", subject or "")).split())


def complaint_ref_in(text: str) -> str | None:
    match = REF_TAG.search(text or "")
    return match.group(1).upper() if match else None


def order_ref_in(text: str) -> str | None:
    match = ORDER_REF.search(text or "")
    return match.group(0).upper() if match else None


def _automated(msg: EmailMessage, address: str) -> bool:
    """Auto-replies, bounces, list and bulk mail: never answered (mail-loop protection)."""
    auto = str(msg.get("Auto-Submitted", "no")).strip().lower()
    precedence = str(msg.get("Precedence", "")).strip().lower()
    return (
        auto != "no"
        or "X-Autoreply" in msg
        or "X-Autorespond" in msg
        or precedence in {"bulk", "list", "junk"}
        # Mailing lists and bulk senders (RFC 2369): newsletters and service notifications
        # carry List-Unsubscribe even without List-Id or Precedence.
        or any(header.lower().startswith("list-") for header in msg)
        or address.split("@")[0].lower() in AUTOMATED_SENDERS
    )


def _body(msg: EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    if not isinstance(part, EmailMessage):
        return ""
    try:
        content = str(part.get_content())
    except (LookupError, UnicodeError):  # unknown or wrong charset: keep what we can read
        payload = part.get_payload(decode=True)
        content = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else ""
    return html_to_text(content) if part.get_content_subtype() == "html" else content


def parse_email(raw: bytes) -> ParsedEmail:
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    assert isinstance(msg, EmailMessage)
    name, address = parseaddr(str(msg.get("From", "")))
    address = address.strip().lower()
    subject = " ".join(str(msg.get("Subject", "") or "").split())
    attachments = [
        ParsedAttachment(
            a.get_filename() or "attachment",
            a.get_content_type(),
            a.get_payload(decode=True) or b"",  # type: ignore[arg-type]
        )
        for a in msg.iter_attachments()
        if isinstance(a, EmailMessage)
    ]
    message_id = str(msg.get("Message-ID", "") or "").strip()
    if not message_id:
        seed = f"{address}|{msg.get('Date')}|{subject}"
        message_id = (
            f"<generated-{hashlib.sha256(seed.encode()).hexdigest()[:32]}@supportnova.local>"
        )
    references = [a for _, a in getaddresses([str(msg.get("References", "") or "")]) if a]
    try:
        date = parsedate_to_datetime(str(msg["Date"])) if msg.get("Date") else None
    except (TypeError, ValueError):
        date = None
    return ParsedEmail(
        message_id=message_id,
        from_address=address,
        from_name=name.strip() or None,
        subject=subject,
        body=strip_quoted(_body(msg)),
        in_reply_to=str(msg.get("In-Reply-To", "") or "").strip() or None,
        references=[f"<{r.strip('<>')}>" for r in references],
        attachments=attachments,
        automated=_automated(msg, address),
        date=date,
    )
