"""E-mails and chat lines are composed from the Customer texts settings."""

from typing import Any

import app_settings
from email_channel.outbound import compose, signature
from support_chat.intake import next_turn


def use_texts(**groups: dict[str, Any]) -> None:
    base = app_settings.defaults()
    texts = base.texts.model_copy(
        update={g: getattr(base.texts, g).model_copy(update=v) for g, v in groups.items()}
    )
    app_settings.override(base.model_copy(update={"texts": texts}))


def test_compose_uses_settings() -> None:
    use_texts(complaint_emails={"acknowledgement": "Got it, {name}: {ref}."})
    body = compose("acknowledgement", name="Ayesha", ref="CMP-1")
    assert body.startswith("Got it, Ayesha: CMP-1.")
    assert body.endswith(signature())


def test_signature_follows_shop_name() -> None:
    base = app_settings.defaults()
    app_settings.override(
        base.model_copy(
            update={"branding": base.branding.model_copy(update={"shop_name": "Nova Mart"})}
        )
    )
    assert signature() == "\n\nKind regards,\nNova Mart Customer Care"


def test_empty_signature_adds_nothing() -> None:
    use_texts(complaint_emails={"signature": ""})
    assert signature() == ""
    assert compose("holding", name="Ayesha", ref="CMP-1").endswith(
        "as soon as the review is complete."
    )


def test_values_with_braces_are_inserted_literally() -> None:
    body = compose("rejected", name="{A}", reason="bad {x}")
    assert "Hello {A}," in body and "bad {x}" in body


def test_fallback_question_from_settings() -> None:
    defaults = app_settings.defaults().texts.chat.fallback_questions
    use_texts(
        chat={"fallback_questions": [defaults[0], "When exactly did it happen?", defaults[2]]}
    )
    result = next_turn(None, order=None, customer_messages=["My charger broke"])
    assert result.reply == "When exactly did it happen?"
