"""Deterministic risk-signal detection (no LLM).

Each signal (Settings → Patterns; defaults in `config/detectors.yaml`) is a list of phrases or
regular expressions matched on word boundaries. The matched phrases are kept as evidence, so a
reviewer can see exactly why a complaint was escalated.
"""

import re
from functools import lru_cache

import app_settings
from app_settings.patterns import joined


@lru_cache(maxsize=8)
def _compiled(lexicon: tuple[tuple[str, str], ...]) -> dict[str, re.Pattern[str]]:
    # (?<!\w) / (?!\w) instead of \b, so patterns may start or end with symbols like "<" or "[".
    return {
        name: re.compile(r"(?<!\w)(?:" + source + r")(?!\w)", re.IGNORECASE)
        for name, source in lexicon
    }


def detect_signals(text: str) -> dict[str, list[str]]:
    """Return {signal: [matched phrases]} for every signal that fired."""
    signals = app_settings.runtime().patterns.signals  # Settings → Patterns
    lexicon = tuple((name, joined(entries)) for name, entries in signals.items())
    found: dict[str, list[str]] = {}
    for name, pattern in _compiled(lexicon).items():
        matches = list(dict.fromkeys(m.group(0).lower() for m in pattern.finditer(text)))
        if matches:
            found[name] = matches[:5]
    return found
