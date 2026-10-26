"""Validation and classifier values in the run-time settings: defaults, limits, fallback."""

import copy
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

import app_settings
from app_settings.model import ValidationSettings


def base() -> dict[str, Any]:
    return app_settings.defaults().validation.model_dump()


def test_defaults_equal_the_yaml() -> None:
    v = app_settings.defaults().validation
    assert v.score_weights.model_dump() == {"critical": 5, "major": 3, "minor": 1}
    assert v.compensation["store_credit"].max_amount == 50
    assert v.compensation["store_credit"].max_pct_of_order == 10
    assert v.compensation["full_refund"].max_amount is None
    assert "PROMISE_CASH_COMPENSATION" in v.never_allowed_actions
    assert len(v.never_allowed_actions) == 7
    assert v.orders_required_for == [
        "DELIVERY",
        "PRODUCT_DEFECT",
        "REFUND",
        "RETURNS_REPLACEMENT",
        "WARRANTY",
    ]
    assert v.escalation_action_levels["ESCALATE_TO_SUPERVISOR"] == 1
    assert (v.classifier_confident, v.classifier_secondary) == (3, 3)
    assert v.signal_boosts["safety_hazard"].model_dump() == {
        "category": "SAFETY",
        "subcategory": "OVERHEATING_BATTERY",
        "weight": 3,
    }


def _set(path: list[str], value: Any) -> Callable[[dict[str, Any]], None]:
    def change(d: dict[str, Any]) -> None:
        target = d
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


def _drop(path: list[str]) -> Callable[[dict[str, Any]], None]:
    def change(d: dict[str, Any]) -> None:
        target = d
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]

    return change


@pytest.mark.parametrize(
    "change",
    [
        _set(["score_weights", "critical"], 0),
        _set(["score_weights", "minor"], 11),
        _set(["score_weights", "critical"], 2),  # below major (3)
        _drop(["compensation", "voucher"]),
        _set(["compensation", "cash"], {"requires_any": ["OFFER_STORE_CREDIT"]}),
        _set(["compensation", "store_credit", "requires_any"], []),
        _set(["compensation", "store_credit", "requires_any"], ["NOT_AN_ACTION"]),
        _set(["compensation", "store_credit", "requires_any"], ["OFFER_STORE_CREDIT"] * 2),
        _set(["compensation", "store_credit", "max_pct_of_order"], 101),
        _set(["compensation", "store_credit", "max_amount"], -1),
        _set(["never_allowed_actions"], ["NOT_AN_ACTION"]),
        _set(["never_allowed_actions"], ["DISCUSS_LIABILITY", "DISCUSS_LIABILITY"]),
        _set(["escalation_action_levels", "ESCALATE_TO_SUPERVISOR"], 0),
        _set(["escalation_action_levels", "ESCALATE_TO_MANAGER"], 6),
        _drop(["escalation_action_levels", "ESCALATE_TO_SPECIALIST"]),
        _set(["classifier_confident"], 0),
        _set(["classifier_secondary"], 11),
        _set(["signal_boosts", "safety_hazard", "weight"], 6),
        _set(
            ["signal_boosts", "not_a_signal"],
            {"category": "SAFETY", "subcategory": "X", "weight": 1},
        ),
        _set(["orders_required_for"], ["DELIVERY", "DELIVERY"]),
    ],
)
def test_limits_refused(change: Callable[[dict[str, Any]], None]) -> None:
    data = copy.deepcopy(base())
    change(data)
    with pytest.raises(ValidationError):
        ValidationSettings.model_validate(data)


def test_too_many_boosts_refused() -> None:
    data = base()
    data["signal_boosts"] = {
        f"s{i}": {"category": "SAFETY", "subcategory": "X", "weight": 1} for i in range(15)
    }
    with pytest.raises(ValidationError):
        ValidationSettings.model_validate(data)


def test_no_limit_is_allowed() -> None:
    data = base()
    data["compensation"]["store_credit"]["max_amount"] = None
    data["compensation"]["store_credit"]["max_pct_of_order"] = None
    assert ValidationSettings.model_validate(data).compensation["store_credit"].max_amount is None


def test_bad_validation_group_resets_only_that_group() -> None:
    s = app_settings.load(
        {"validation": {"classifier_confident": 0}, "email": {"mailbox_check_seconds": 120}}
    )
    assert s.validation.classifier_confident == 3
    assert s.email.mailbox_check_seconds == 120
