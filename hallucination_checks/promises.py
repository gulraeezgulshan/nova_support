"""Unsupported-promise detection in customer-facing text (SRS Step 34).

A sentence is a *promise* when it commits to an outcome ("we will refund", "you'll receive a
replacement", "within 24 hours") and is not made conditional ("once we verify", "if you are
eligible"). Each promise must be backed by the rule matrix (a remedy action the rules
require) or, for deadlines, by a policy passage, the SLA or the rule follow-up time.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from python_validation.types import validation_config

SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass(frozen=True)
class Promise:
    kind: str  # refund | replacement | compensation | policy_exception | deadline
    sentence: str
    detail: str


@lru_cache
def _patterns() -> dict[str, Any]:
    cfg = validation_config()["promises"]
    return {
        "commitment": re.compile(cfg["commitment"], re.IGNORECASE),
        "conditional": re.compile(cfg["conditional"], re.IGNORECASE),
        "deadline": re.compile(cfg["deadline"], re.IGNORECASE),
        "kinds": {
            kind: (re.compile(spec["pattern"], re.IGNORECASE), tuple(spec["supported_by"]))
            for kind, spec in cfg["kinds"].items()
        },
    }


def find_promises(text: str) -> list[Promise]:
    patterns = _patterns()
    promises: list[Promise] = []
    for sentence in (s.strip() for s in SENTENCE.split(text or "")):
        if not sentence or not patterns["commitment"].search(sentence):
            continue
        if patterns["conditional"].search(sentence):
            continue
        for kind, (pattern, _) in patterns["kinds"].items():
            match = pattern.search(sentence)
            if match:
                promises.append(Promise(kind, sentence, match.group(0)))
        for match in patterns["deadline"].finditer(sentence):
            promises.append(Promise("deadline", sentence, match.group(0)))
    return promises


def normalise_duration(amount: str, unit: str) -> tuple[int, str]:
    unit = unit.lower().rstrip("s")
    hours = {"hour": 1, "day": 24, "week": 168}[unit]
    return int(amount) * hours, unit


def unsupported_promises(
    promises: Iterable[Promise],
    required_actions: set[str],
    allowed_durations_hours: set[int],
    policy_text: str,
) -> list[Promise]:
    """Promises not backed by a required remedy action or a documented timeline."""
    kinds = _patterns()["kinds"]
    deadline = _patterns()["deadline"]
    policy_text = policy_text.lower()
    unsupported = []
    for promise in promises:
        if promise.kind == "deadline":
            match = deadline.search(promise.detail)
            if match and match.group(1):
                hours, _ = normalise_duration(match.group(1), match.group(3))
                phrase = f"{match.group(1)} {(match.group(2) or '')}{match.group(3)}".lower()
                singular = phrase.rstrip("s")
                if hours in allowed_durations_hours or singular in policy_text:
                    continue
            unsupported.append(promise)
        elif not required_actions & set(kinds[promise.kind][1]):
            unsupported.append(promise)
    return unsupported
