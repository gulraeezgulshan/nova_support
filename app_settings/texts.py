"""Customer texts (Settings → Customer texts): which placeholders each text may use.

One registry serves the settings checks, the readers, the API and the page, so a placeholder
is never allowed in one place and refused in another. Stored texts are filled with `render`,
which inserts values literally: a product called "{X}" can never break an e-mail.
"""

from string import Formatter

ORDER_EMAIL_KINDS: tuple[str, ...] = (
    "placed",
    "shipped",
    "delayed",
    "delivered",
    "cancelled",
    "returned",
    "return_refused",
)
_ORDER = ("name", "order_ref", "product", "amount", "date", "shop")

# path → (allowed placeholders, required placeholders)
PLACEHOLDERS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    **{
        f"order_emails.{k}.{part}": (_ORDER, ())
        for k in ORDER_EMAIL_KINDS
        for part in ("subject", "body")
    },
    "complaint_emails.acknowledgement": (("name", "ref", "shop"), ("ref",)),
    "complaint_emails.holding": (("name", "ref", "shop"), ("ref",)),
    "complaint_emails.rejected": (("name", "reason", "shop"), ("reason",)),
    "complaint_emails.duplicate": (("name", "ref", "shop"), ("ref",)),
    "complaint_emails.signature": (("shop",), ()),
    "chat.greeting": (("shop",), ()),
    "chat.ask_what_happened": (("product",), ()),
    "chat.fallback_questions": ((), ()),
    "chat.neutral_question": ((), ()),
    "chat.summary_lead": ((), ()),
    "chat.faq_follow_up": ((), ()),
    "chat.added_to_complaint": (("ref",), ("ref",)),
    "chat.submitted": (("ref",), ("ref",)),
}

SAMPLES: dict[str, str] = {
    "name": "Ayesha",
    "order_ref": "ORD-240001",
    "product": "AeroBook 14",
    "amount": "PKR 249,999",
    "date": "12 Nov 2026",
    "ref": "CMP-000123",
    "reason": "Description is too short to act on.",
}


def label(path: str, index: int | None = None) -> str:
    """How errors name a text, e.g. 'Order e-mail shipped, body' or 'Chat submitted'."""
    group, *rest = path.split(".")
    if group == "order_emails":
        return f"Order e-mail {rest[0]}, {rest[1]}"
    if group == "complaint_emails":
        return f"Complaint e-mail {rest[0]}"
    if rest[0] == "fallback_questions":
        return f"Chat fallback question {index}"
    return f"Chat {rest[0].replace('_', ' ')}"


def _fields(text: str) -> list[str]:
    return [name for _, name, _, _ in Formatter().parse(text) if name is not None]


def placeholder_problem(text: str, allowed: tuple[str, ...]) -> str | None:
    """Why this text cannot be filled, or None."""
    try:
        names = _fields(text)
    except ValueError:
        return "braces must wrap a placeholder name"
    for name in names:
        if not name.isidentifier():
            return "braces must wrap a placeholder name"
        if name not in allowed:
            options = ", ".join(f"{{{a}}}" for a in allowed) or "none"
            return f"unknown placeholder {{{name}}}; use one of {options}."
    return None


def render(text: str, **values: str) -> str:
    """Fill the placeholders; values are inserted as they are, never read as placeholders."""
    parts = []
    for literal, name, _, _ in Formatter().parse(text):
        parts.append(literal)
        if name is not None:
            parts.append(values.get(name, f"{{{name}}}"))
    return "".join(parts)
