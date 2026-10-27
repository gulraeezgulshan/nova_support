"""Analytics, intake and shop values in the run-time settings: defaults, limits, fallback."""

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

import app_settings
from app_settings.model import AnalyticsSettings, IntakeSettings, ShopSettings
from storefront.faq import filled


def _with(model: type[BaseModel], group: str, **changes: Any) -> None:
    data = {**getattr(app_settings.defaults(), group).model_dump(), **changes}
    model.model_validate(data)


def test_defaults_equal_today() -> None:
    d = app_settings.defaults()
    a, i, s = d.analytics, d.intake, d.shop
    assert (a.trend_window_days, a.trend_min_count, a.trend_rise_ratio) == (7, 3, 1.5)
    assert (a.recurring_min_count, a.dashboard_list_limit) == (3, 10)
    assert a.watched_categories == ["DELIVERY", "BILLING"]
    assert a.first_response_statuses == [
        "assigned",
        "in_progress",
        "awaiting_customer",
        "escalated",
        "resolved",
    ]
    assert a.resolved_statuses == ["resolved", "closed"]
    assert (i.near_duplicate_min_ratio, i.related_min_similarity, i.duplicate_window_days) == (
        88,
        0.80,
        30,
    )
    assert (i.repeat_window_days, i.repeat_min_gap_hours) == (60, 24)
    assert (i.min_title_chars, i.min_description_chars, i.min_description_words) == (5, 20, 5)
    assert (i.max_description_chars, i.max_attachments, i.max_attachment_mb) == (5000, 5, 5)
    assert (i.chat_max_questions, i.chat_max_message_chars, i.chat_max_customer_messages) == (
        6,
        2000,
        30,
    )
    assert i.import_max_rows == 1000
    assert s.best_seller_days == 90
    assert [x.name for x in s.socials] == ["Instagram", "X", "YouTube"]
    assert len(s.faq) == 7
    assert "{standard_days}" in s.faq[0].answer
    assert d.orders.delay_wait_steps == 3


ANALYTICS_BAD = [
    ("trend_window_days", 0),
    ("trend_window_days", 91),
    ("trend_min_count", 0),
    ("trend_min_count", 101),
    ("trend_rise_ratio", 0.9),
    ("trend_rise_ratio", 10.1),
    ("recurring_min_count", 0),
    ("recurring_min_count", 101),
    ("dashboard_list_limit", 4),
    ("dashboard_list_limit", 51),
    ("watched_categories", ["DELIVERY", "DELIVERY"]),
    ("watched_categories", [f"C{i}" for i in range(21)]),
    ("first_response_statuses", []),
    ("resolved_statuses", ["done"]),
    ("resolved_statuses", ["closed", "closed"]),
]
INTAKE_BAD = [
    ("near_duplicate_min_ratio", 69),
    ("near_duplicate_min_ratio", 101),
    ("related_min_similarity", 0.49),
    ("related_min_similarity", 1.0),
    ("duplicate_window_days", 0),
    ("duplicate_window_days", 366),
    ("repeat_window_days", 0),
    ("repeat_min_gap_hours", 169),
    ("min_title_chars", 2),
    ("min_title_chars", 21),
    ("min_description_chars", 9),
    ("min_description_chars", 201),
    ("min_description_words", 0),
    ("min_description_words", 31),
    ("max_description_chars", 499),
    ("max_description_chars", 5001),
    ("max_attachments", -1),
    ("max_attachments", 11),
    ("max_attachment_mb", 0),
    ("max_attachment_mb", 11),
    ("chat_max_questions", 1),
    ("chat_max_questions", 13),
    ("chat_max_message_chars", 199),
    ("chat_max_message_chars", 2001),
    ("chat_max_customer_messages", 4),
    ("chat_max_customer_messages", 101),
    ("import_max_rows", 9),
    ("import_max_rows", 5001),
]
SHOP_BAD = [
    ("best_seller_days", 6),
    ("best_seller_days", 366),
    ("socials", [{"name": "X", "url": "http://x.com"}]),
    ("socials", [{"name": "", "url": "https://x.com"}]),
    ("socials", [{"name": f"S{i}", "url": "https://x.com"} for i in range(9)]),
    ("faq", []),
    ("faq", [{"question": "Why is that?", "answer": "Because it is."}] * 21),
    ("faq", [{"question": "Why", "answer": "Because it is."}]),
]


@pytest.mark.parametrize(("field", "value"), ANALYTICS_BAD)
def test_analytics_limits(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        _with(AnalyticsSettings, "analytics", **{field: value})


@pytest.mark.parametrize(("field", "value"), INTAKE_BAD)
def test_intake_limits(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        _with(IntakeSettings, "intake", **{field: value})


@pytest.mark.parametrize(("field", "value"), SHOP_BAD)
def test_shop_limits(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        _with(ShopSettings, "shop", **{field: value})


def test_delay_wait_limits() -> None:
    orders = type(app_settings.defaults().orders)
    for value in (0, 21):
        with pytest.raises(ValidationError):
            _with(orders, "orders", delay_wait_steps=value)


@pytest.mark.parametrize(
    "answer",
    [
        "Arrives in {foo} days.",
        "Arrives in { } days.",
        "Arrives in {0} days.",
        "Arrives in { days.",
        "Arrives in } days.",
    ],
)
def test_faq_braces_refused(answer: str) -> None:
    faq = [{"question": "How long is it?", "answer": answer}]
    with pytest.raises(ValidationError, match="FAQ 1: "):
        _with(ShopSettings, "shop", faq=faq)


def test_faq_unknown_placeholder_message() -> None:
    faq = [{"question": "How long is it?", "answer": "in {foo} days"}]
    with pytest.raises(ValidationError, match=r"FAQ 1: unknown placeholder \{foo\}"):
        _with(ShopSettings, "shop", faq=faq)


def test_faq_known_placeholder_accepted() -> None:
    faq = [{"question": "How long is it?", "answer": "within {standard_days} days"}]
    _with(ShopSettings, "shop", faq=faq)


def test_filled() -> None:
    assert filled("{standard_days} days") == "5 days"


def test_bad_intake_group_resets_only_that_group() -> None:
    s = app_settings.load(
        {
            "intake": {"min_description_chars": 200, "max_description_chars": 150},
            "email": {"mailbox_check_seconds": 120},
        }
    )
    assert s.intake == app_settings.defaults().intake
    assert s.email.mailbox_check_seconds == 120
