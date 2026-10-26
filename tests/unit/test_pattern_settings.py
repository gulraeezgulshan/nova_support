"""Text patterns in the run-time settings: defaults, limits, safety checks, fallback."""

import copy
from collections.abc import Callable
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

import app_settings
from app_settings.model import PatternEntry, PatternSettings
from app_settings.patterns import entry_source, regex_problem
from src.core.config import ROOT_DIR


def base() -> dict[str, Any]:
    return app_settings.defaults().patterns.model_dump()


def _yaml(name: str) -> Any:
    with (ROOT_DIR / "config" / name).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_defaults_equal_the_yaml() -> None:
    p = app_settings.defaults().patterns
    promises = _yaml("validation.yaml")["promises"]
    assert len(p.signals) == 14
    assert p.signals["safety_hazard"][0] == PatternEntry(text="overheat\\w*", mode="regex")
    assert p.classifier["DELIVERY"]["LOST_PARCEL"][0].weight == 3
    assert len(p.promises.commitment) == 1
    assert p.promises.commitment[0].text == promises["commitment"]
    assert p.promises.deadline == promises["deadline"]
    entries = [e for v in p.signals.values() for e in v]
    entries += [e for subs in p.classifier.values() for v in subs.values() for e in v]
    entries += p.promises.commitment + p.promises.conditional
    entries += [e for v in p.promises.kinds.values() for e in v]
    assert {e.mode for e in entries} == {"regex"}


def _set(path: list[str | int], value: Any) -> Callable[[dict[str, Any]], None]:
    def change(d: dict[str, Any]) -> None:
        target: Any = d
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


def _drop(path: list[str | int]) -> Callable[[dict[str, Any]], None]:
    def change(d: dict[str, Any]) -> None:
        target: Any = d
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]

    return change


def _regex(text: str) -> dict[str, str]:
    return {"text": text, "mode": "regex"}


def _first_signal(entry: dict[str, Any]) -> Callable[[dict[str, Any]], None]:
    return _set(["signals", "injury", 0], entry)


@pytest.mark.parametrize(
    "change",
    [
        _first_signal(_regex("(unclosed")),
        _first_signal(_regex("(a+)+")),
        _first_signal(_regex("(\\w+\\s?)*")),
        _first_signal(_regex("x" * 301)),
        _first_signal(_regex("   ")),
        _set(["signals", "injury", 1], _regex("injur\\w*")),  # duplicate of entry 1
        _set(["signals", "injury"], []),
        _set(["signals", "injury"], [_regex(f"word{i}") for i in range(81)]),
        _set(["signals", "not_a_signal"], [_regex("x")]),
        _drop(["signals", "injury"]),
        _set(["classifier", "DELIVERY", "LOST_PARCEL", 0, "weight"], 0),
        _set(["classifier", "DELIVERY", "LOST_PARCEL", 0, "weight"], 4),
        _set(
            ["classifier", "DELIVERY", "LOST_PARCEL"],
            [{"text": f"w{i}", "mode": "phrase", "weight": 1} for i in range(41)],
        ),
        _set(["promises", "kinds", "cash"], [_regex("cash")]),
        _drop(["promises", "kinds", "refund"]),
        _set(["promises", "commitment"], []),
        _set(["promises", "deadline"], "within (\\d+) days"),
    ],
)
def test_limits_refused(change: Callable[[dict[str, Any]], None]) -> None:
    data = copy.deepcopy(base())
    change(data)
    with pytest.raises(ValidationError):
        PatternSettings.model_validate(data)


def test_bounded_repeat_allowed() -> None:
    assert regex_problem("arriv\\w* (?:\\w+ ){0,4}late") is None
    assert regex_problem("[a+]+") is None  # a character class is not a group


def test_error_names_the_place() -> None:
    data = base()
    data["signals"]["injury"][3] = _regex("(x")
    with pytest.raises(ValidationError, match="injury, entry 4: regex does not compile"):
        PatternSettings.model_validate(data)


def test_entry_source() -> None:
    assert entry_source(PatternEntry(text="a.b", mode="phrase")) == "a\\.b"
    assert entry_source(PatternEntry(text="money back", mode="phrase"), bounded=True) == (
        r"(?<!\w)money\ back(?!\w)"
    )
    assert entry_source(PatternEntry(text="fire\\w*", mode="regex")) == "fire\\w*"


def test_bad_patterns_group_resets_only_that_group() -> None:
    s = app_settings.load(
        {"patterns": {"signals": {"injury": []}}, "email": {"mailbox_check_seconds": 120}}
    )
    assert s.patterns == app_settings.defaults().patterns
    assert s.email.mailbox_check_seconds == 120
