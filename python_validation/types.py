"""Shared types for the Ground-Truth Validation Pipeline."""

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from functools import lru_cache
from typing import Any

import yaml

from src.core.config import ROOT_DIR


class CheckStatus(StrEnum):
    PASS = "pass"  # noqa: S105 - a check status, not a password
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"  # could not be checked (e.g. Python cannot classify independently)


class Severity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class Verdict(StrEnum):
    VERIFIED = "verified"  # every check passed or only warned
    CORRECTED = "corrected"  # Python enforced rule values (priority, escalation, actions)
    NEEDS_REVIEW = "needs_review"  # needs a human decision


@dataclass
class CheckResult:
    code: str
    name: str
    status: CheckStatus
    severity: Severity
    message: str
    expected: Any = None
    actual: Any = None
    evidence: list[str] = field(default_factory=list)
    # True when Python can fix the recommendation itself (e.g. raise the priority to the rule
    # minimum) instead of needing a reviewer.
    correctable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@lru_cache
def validation_config() -> dict[str, Any]:
    with (ROOT_DIR / "config" / "validation.yaml").open(encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle)
    return data
