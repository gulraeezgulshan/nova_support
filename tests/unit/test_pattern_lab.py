"""The pattern lab: time-limited runs, the text test, the dataset check and the stress check."""

import operator
import re
import time
from typing import Any

import pytest

import app_settings
from pattern_lab.lab import dataset_check, stress_check, try_text
from pattern_lab.sandbox import TooSlowError, run_limited
from sample_complaints.evaluate import yaml_taxonomy


def _slow() -> bool:
    return re.fullmatch("(a|aa)+$", "a" * 40 + "b") is not None


def _settings() -> dict[str, Any]:
    return app_settings.defaults().model_dump()


def _draft(change: Any = None) -> dict[str, Any]:
    data = app_settings.defaults().patterns.model_dump()
    if change:
        change(data)
    return data


def _phrase(text: str) -> dict[str, str]:
    return {"text": text, "mode": "phrase"}


def test_run_limited_returns_result() -> None:
    assert run_limited(operator.add, (2, 3), 5) == 5


def test_run_limited_stops_slow_work() -> None:
    started = time.monotonic()
    with pytest.raises(TooSlowError):
        run_limited(_slow, (), 1)
    assert time.monotonic() - started < 35


def test_try_text_shows_draft_difference() -> None:
    draft = _draft(lambda d: d["signals"]["safety_hazard"].append(_phrase("caught fire")))
    result = try_text(_settings(), draft, "The charger caught fire", yaml_taxonomy())
    assert "caught fire" in result["draft"]["signals"]["safety_hazard"]
    assert "caught fire" not in result["saved"]["signals"].get("safety_hazard", [])


def test_dataset_check_defaults_are_equal() -> None:
    result = dataset_check(_settings(), _draft(), yaml_taxonomy())
    assert result["total"] == 536
    for delta in result["signals"]:
        assert delta["saved"] == delta["draft"]
        assert delta["gained"] == delta["lost"] == []
    assert result["classifier"]["saved_correct"] == result["classifier"]["draft_correct"]
    assert result["escalation"]["saved"] == result["escalation"]["draft"]


def test_dataset_check_detects_gain() -> None:
    draft = _draft(lambda d: d["signals"]["legal_threat"].append(_phrase("order")))
    result = dataset_check(_settings(), draft, yaml_taxonomy())
    delta = next(d for d in result["signals"] if d["signal"] == "legal_threat")
    assert delta["draft"] > delta["saved"]
    assert 0 < len(delta["gained"]) <= 10


def test_defaults_pass_stress_check() -> None:
    run_limited(stress_check, (_draft(),), 2)


def test_stress_check_refuses_slow() -> None:
    draft = _draft(lambda d: d["signals"]["injury"].append({"text": "(a|aa)+", "mode": "regex"}))
    with pytest.raises(TooSlowError):
        run_limited(stress_check, (draft,), 2)


def test_lab_restores_the_runtime() -> None:
    before = app_settings.runtime()
    try_text(_settings(), _draft(), "hello", yaml_taxonomy())
    assert app_settings.runtime() is before
