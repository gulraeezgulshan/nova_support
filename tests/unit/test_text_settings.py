"""Customer texts in the run-time settings: defaults reproduce today, placeholder checks."""

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import app_settings
from app_settings.model import TextSettings
from app_settings.texts import SAMPLES, render

TODAY = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "customer_texts_today.json").read_text("utf-8")
)
VALUES = {**SAMPLES, "shop": "VoltHaven"}


def base() -> dict[str, Any]:
    return app_settings.defaults().texts.model_dump()


def test_defaults_reproduce_today() -> None:
    t = app_settings.defaults().texts
    for kind, text in t.order_emails.items():
        assert render(text.subject, **VALUES) == TODAY["order_emails"][kind]["subject"]
        assert render(text.body, **VALUES) == TODAY["order_emails"][kind]["body"]
    signature = "\n\n" + render(t.complaint_emails.signature, **VALUES)
    assert signature == TODAY["signature"]
    for kind in ("acknowledgement", "holding", "rejected", "duplicate"):
        body = render(getattr(t.complaint_emails, kind), **VALUES)
        assert body + signature == TODAY["complaint_emails"][kind]
    for line, expected in TODAY["chat"].items():
        value = getattr(t.chat, line)
        if isinstance(value, list):
            assert [render(v, **VALUES) for v in value] == expected
        else:
            assert render(value, **VALUES) == expected


def _set(path: list[str | int], value: Any) -> Callable[[dict[str, Any]], None]:
    def change(d: dict[str, Any]) -> None:
        target: Any = d
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


def _refused(change: Callable[[dict[str, Any]], None], match: str | None = None) -> None:
    data = copy.deepcopy(base())
    change(data)
    with pytest.raises(ValidationError, match=match):
        TextSettings.model_validate(data)


def test_unknown_placeholder_refused() -> None:
    _refused(
        _set(["order_emails", "shipped", "body"], "Hello {name}, your {foo} has shipped today."),
        r"Order e-mail shipped, body: unknown placeholder \{foo\}; use one of \{name\}, "
        r"\{order_ref\}, \{product\}, \{amount\}, \{date\}, \{shop\}\.",
    )


@pytest.mark.parametrize(
    "text",
    [
        "Hello there { friend",
        "Hello there } friend",
        "Hello there {} friend",
        "Hello there {0} friend",
        "Hello there {shop.x} friend",
        "Hello there {shop[0]} friend",
    ],
)
def test_broken_braces_refused(text: str) -> None:
    _refused(_set(["chat", "greeting"], text), "Chat greeting: ")


def test_required_placeholders() -> None:
    _refused(
        _set(["complaint_emails", "acknowledgement"], "Hello {name}, we have your complaint."),
        r"Complaint e-mail acknowledgement must include \{ref\}\.",
    )
    _refused(
        _set(["complaint_emails", "rejected"], "Hello {name}, we could not open a complaint."),
        r"Complaint e-mail rejected must include \{reason\}\.",
    )
    _refused(
        _set(["chat", "submitted"], "Thanks, it is sent."), r"Chat submitted must include \{ref\}\."
    )


def test_fallback_questions_exactly_three() -> None:
    _refused(_set(["chat", "fallback_questions"], ["What happened?", "When?"]))
    _refused(_set(["chat", "fallback_questions"], ["What happened?", "When?", "Why?", "How?"]))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (["order_emails", "placed", "subject"], "x" * 4),
        (["order_emails", "placed", "subject"], "x" * 151),
        (["order_emails", "placed", "body"], "x" * 19),
        (["order_emails", "placed", "body"], "x" * 2001),
        (["complaint_emails", "signature"], "x" * 301),
        (["chat", "neutral_question"], "x" * 4),
        (["chat", "neutral_question"], "x" * 501),
    ],
)
def test_lengths(path: list[str | int], value: str) -> None:
    _refused(_set(path, value))


def test_order_email_kinds_exact() -> None:
    def drop(d: dict[str, Any]) -> None:
        del d["order_emails"]["placed"]

    _refused(drop)
    extra = {"subject": "Refunded order", "body": "Hello {name}, your order was refunded."}
    _refused(_set(["order_emails", "refunded"], extra))


def test_empty_signature_allowed() -> None:
    data = base()
    data["complaint_emails"]["signature"] = ""
    assert TextSettings.model_validate(data).complaint_emails.signature == ""


def test_render_inserts_values_literally() -> None:
    assert render("Hi {name}", name="{x}") == "Hi {x}"


def test_bad_texts_group_resets_only_that_group() -> None:
    s = app_settings.load(
        {"texts": {"chat": {"greeting": "x"}}, "email": {"mailbox_check_seconds": 120}}
    )
    assert s.texts == app_settings.defaults().texts
    assert s.email.mailbox_check_seconds == 120
