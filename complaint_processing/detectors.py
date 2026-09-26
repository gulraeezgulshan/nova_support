"""Deterministic risk-signal detection (no LLM).

Each signal in `config/detectors.yaml` is a list of regular expressions matched on word
boundaries. The matched phrases are kept as evidence, so a reviewer can see exactly why a
complaint was escalated.
"""

import re
from functools import lru_cache

from src.core.domain import signal_lexicons


@lru_cache
def _compiled() -> dict[str, re.Pattern[str]]:
    # (?<!\w) / (?!\w) instead of \b, so patterns may start or end with symbols like "<" or "[".
    return {
        name: re.compile(r"(?<!\w)(?:" + "|".join(spec.patterns) + r")(?!\w)", re.IGNORECASE)
        for name, spec in signal_lexicons().items()
    }


def detect_signals(text: str) -> dict[str, list[str]]:
    """Return {signal: [matched phrases]} for every signal that fired."""
    found: dict[str, list[str]] = {}
    for name, pattern in _compiled().items():
        matches = list(dict.fromkeys(m.group(0).lower() for m in pattern.finditer(text)))
        if matches:
            found[name] = matches[:5]
    return found
