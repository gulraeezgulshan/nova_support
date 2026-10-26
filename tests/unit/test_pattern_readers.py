"""The detector, classifier and promise checks read the patterns from the run-time settings."""

from collections.abc import Callable
from typing import Any

import app_settings
from app_settings.model import PatternSettings
from complaint_processing.detectors import detect_signals
from hallucination_checks.promises import find_promises, sentence_checks
from python_validation.classifier import classify
from support_chat.intake import deadline_pattern


def _with_patterns(change: Callable[[dict[str, Any]], None]) -> None:
    base = app_settings.defaults()
    data = base.patterns.model_dump()
    change(data)
    app_settings.override(
        base.model_copy(update={"patterns": PatternSettings.model_validate(data)})
    )


def _phrase(text: str) -> dict[str, str]:
    return {"text": text, "mode": "phrase"}


def _taxonomy() -> dict[str, list[str]]:
    return {c: list(s) for c, s in app_settings.defaults().patterns.classifier.items()}


def test_added_signal_phrase_fires() -> None:
    assert "caught fire" not in detect_signals("It caught fire overnight").get("safety_hazard", [])
    _with_patterns(lambda d: d["signals"]["safety_hazard"].append(_phrase("caught fire")))
    assert "caught fire" in detect_signals("It caught fire overnight")["safety_hazard"]


def test_phrase_entries_match_literally() -> None:
    def change(d: dict[str, Any]) -> None:
        d["signals"]["legal_threat"].append(_phrase("a.b"))
        d["promises"]["kinds"]["compensation"].append(_phrase("a+b deal"))

    _with_patterns(change)
    assert detect_signals("see a.b now").get("legal_threat") == ["a.b"]
    assert "legal_threat" not in detect_signals("see axb now")
    found = find_promises("We will give you the a+b deal.")
    assert [(p.kind, p.detail) for p in found] == [("compensation", "a+b deal")]
    assert find_promises("We will give you the aab deal.") == []


def test_classifier_uses_saved_phrases() -> None:
    def change(d: dict[str, Any]) -> None:
        d["classifier"]["DELIVERY"]["LOST_PARCEL"].append({**_phrase("zebra parcel"), "weight": 3})

    _with_patterns(change)
    result = classify("my zebra parcel", {}, _taxonomy())
    assert result.primary is not None
    assert result.primary.subcategory == "LOST_PARCEL"


def test_deadline_from_settings() -> None:
    assert deadline_pattern().search("in 2 fortnights") is None

    def change(d: dict[str, Any]) -> None:
        d["promises"]["deadline"] = "\\b(?:in) (\\d+) (business )?(fortnights?)\\b"

    _with_patterns(change)
    assert deadline_pattern().search("in 2 fortnights")


def test_sentence_checks() -> None:
    first, second = sentence_checks("We will refund you. If eligible, we will refund you.")
    assert (first.commitment, first.conditional, first.kinds) == (True, False, ["refund"])
    assert second.conditional is True


def test_change_applies_without_restart() -> None:
    assert "legal_threat" not in detect_signals("the zebra clause")
    _with_patterns(lambda d: d["signals"]["legal_threat"].append(_phrase("zebra clause")))
    assert "legal_threat" in detect_signals("the zebra clause")
    _with_patterns(lambda d: None)
    assert "legal_threat" not in detect_signals("the zebra clause")
