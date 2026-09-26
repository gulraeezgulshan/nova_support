"""Independent keyword classifier for the Ground-Truth Validation Pipeline.

The GenAI category is never taken on trust: Python scores every subcategory with the
weighted phrase lists in `config/classification.yaml` plus decisive risk signals, and the
validation compares the two. When the text gives Python too little to go on, the result is
`unknown` rather than a guess, and the check reports that honestly.
"""

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml

from complaint_rules.engine import routing_config
from src.core.config import ROOT_DIR

CONFIG_FILE = ROOT_DIR / "config" / "classification.yaml"
# Issues that outrank everything else when choosing the primary issue (RTG-RUL-01 section 3).
CRITICAL_CATEGORIES = ("SAFETY", "PRIVACY")


@dataclass(frozen=True)
class Candidate:
    category: str
    subcategory: str
    score: int
    evidence: tuple[str, ...]


@dataclass
class Classification:
    confidence: str  # confident | tentative | unknown
    primary: Candidate | None
    secondary: list[Candidate] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def categories(self) -> list[str]:
        """Primary first, then secondary categories."""
        found = [self.primary] if self.primary else []
        return [c.category for c in found + self.secondary]

    def to_dict(self) -> dict[str, Any]:
        def cand(c: Candidate | None) -> dict[str, Any] | None:
            return (
                None
                if c is None
                else {
                    "category": c.category,
                    "subcategory": c.subcategory,
                    "score": c.score,
                    "evidence": list(c.evidence),
                }
            )

        return {
            "confidence": self.confidence,
            "primary": cand(self.primary),
            "secondary": [cand(c) for c in self.secondary],
            "top_candidates": [cand(c) for c in self.candidates[:5]],
        }


@dataclass(frozen=True)
class _Pattern:
    weight: int
    regex: re.Pattern[str]


@dataclass(frozen=True)
class _Config:
    confident: int
    secondary: int
    patterns: dict[tuple[str, str], list[_Pattern]]
    boosts: dict[str, tuple[str, str, int]]


@lru_cache
def _config() -> _Config:
    with CONFIG_FILE.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    patterns: dict[tuple[str, str], list[_Pattern]] = {}
    for category, subs in data["subcategories"].items():
        for subcategory, entries in subs.items():
            patterns[(category, subcategory)] = [
                _Pattern(int(weight), re.compile(rf"(?<!\w)(?:{regex})(?!\w)", re.IGNORECASE))
                for weight, regex in entries
            ]
    boosts = {name: (c, s, int(w)) for name, (c, s, w) in data.get("signal_boosts", {}).items()}
    return _Config(
        data["thresholds"]["confident"], data["thresholds"]["secondary"], patterns, boosts
    )


def _severity(category: str) -> int:
    """Lower is more severe, following the department routing order."""
    routing = routing_config()
    department = routing.category_default_department.get(category, routing.fallback_department)
    order = routing.severity_order
    return order.index(department) if department in order else len(order)


def classify(text: str, signals: dict[str, Any], taxonomy: dict[str, list[str]]) -> Classification:
    """`taxonomy` maps active categories to their active subcategories."""
    config = _config()
    scores: dict[tuple[str, str], int] = {}
    evidence: dict[tuple[str, str], list[str]] = {}
    for key, patterns in config.patterns.items():
        category, subcategory = key
        if subcategory not in taxonomy.get(category, []):
            continue  # deactivated or removed in the live taxonomy
        for pattern in patterns:
            match = pattern.regex.search(text)
            if match:
                scores[key] = scores.get(key, 0) + pattern.weight
                evidence.setdefault(key, []).append(match.group(0).lower())
    for signal, (category, subcategory, weight) in config.boosts.items():
        if signals.get(signal) and subcategory in taxonomy.get(category, []):
            key = (category, subcategory)
            scores[key] = scores.get(key, 0) + weight
            evidence.setdefault(key, []).append(f"signal:{signal}")

    candidates = sorted(
        (Candidate(c, s, score, tuple(evidence[(c, s)])) for (c, s), score in scores.items()),
        key=lambda cand: (-cand.score, _severity(cand.category)),
    )
    best_per_category: dict[str, Candidate] = {}
    for cand in candidates:
        best_per_category.setdefault(cand.category, cand)

    confident = [c for c in best_per_category.values() if c.score >= config.confident]
    if not candidates:
        return Classification("unknown", None, [], [])
    if not confident:
        return Classification("tentative", candidates[0], [], candidates)

    critical = [c for c in confident if c.category in CRITICAL_CATEGORIES]
    primary = min(critical, key=lambda c: _severity(c.category)) if critical else confident[0]
    secondary = [
        c
        for c in best_per_category.values()
        if c.category != primary.category and c.score >= config.secondary
    ]
    return Classification("confident", primary, secondary, candidates)
