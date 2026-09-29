"""Runtime settings: defaults equal today's behaviour; limits and single-line text."""

import pytest
from pydantic import ValidationError

from app_settings import RuntimeSettings, defaults


def test_defaults_are_todays_behaviour() -> None:
    d = defaults()
    assert (d.email.mailbox_check_seconds, d.email.outbox_flush_seconds) == (60, 30)
    assert d.email.auto_replies and d.ai.auto_analysis
    assert d.ai.retrieval_limit == 8
    assert (d.operations.sla_scan_minutes, d.operations.verified_min_score) == (5, 80)
    assert d.operations.always_review_escalation_level == 4
    assert d.branding.shop_name == "VoltHaven Electronics"
    assert d.branding.console_name == "SupportNova"
    assert d.branding.shop_logo_key is None and d.branding.console_logo_key is None


def with_group(group: str, **values: object) -> dict[str, object]:
    data = defaults().model_dump()
    data[group] = {**data[group], **values}
    return data


@pytest.mark.parametrize(
    ("group", "field", "value"),
    [
        ("email", "mailbox_check_seconds", 59),
        ("email", "outbox_flush_seconds", 601),
        ("ai", "retrieval_limit", 21),
        ("operations", "verified_min_score", 49),
        ("operations", "always_review_escalation_level", 6),
        ("branding", "shop_name", ""),
        ("branding", "support_email", "not-an-email"),
    ],
)
def test_out_of_range_values_are_rejected(group: str, field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        RuntimeSettings.model_validate(with_group(group, **{field: value}))


def test_text_must_be_one_line() -> None:  # from_name reaches the e-mail From header
    with pytest.raises(ValidationError):
        RuntimeSettings.model_validate(with_group("email", from_name="Care\r\nBcc: x@y.z"))


def test_model_must_belong_to_the_provider() -> None:
    with pytest.raises(ValidationError, match="Anthropic model"):
        RuntimeSettings.model_validate(with_group("ai", provider="openai", model="claude-opus-5"))
    ok = RuntimeSettings.model_validate(with_group("ai", provider="openai", model="gpt-5"))
    assert ok.ai.model == "gpt-5"


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        RuntimeSettings.model_validate(with_group("email", password="x"))


def test_order_defaults() -> None:
    o = defaults().orders
    assert (o.auto_advance, o.step_minutes, o.delay_chance_pct, o.lost_chance_pct) == (
        True,
        2,
        10,
        0,
    )
    assert o.emails and o.fallback_pkr_rate == 280


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("step_minutes", 0),
        ("delay_chance_pct", 101),
        ("lost_chance_pct", 21),
        ("fallback_pkr_rate", 0),
    ],
)
def test_order_limits(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        RuntimeSettings.model_validate(with_group("orders", **{field: value}))
