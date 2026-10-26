"""Text-pattern helpers shared by the settings model, the readers and the pattern lab.

An entry is a plain phrase (matched literally) or a regular expression. Regexes are checked
before they are stored: they must compile and must not nest unbounded repeats such as
`(a+)+`, which can take exponential time on crafted complaint text.
"""

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app_settings.model import PatternEntry

PROMISE_KINDS: tuple[str, ...] = ("refund", "replacement", "compensation", "policy_exception")
SLOW = "may be very slow on some texts"
_UNBOUNDED = re.compile(r"[+*]|\{\d+,\}")


def entry_source(entry: "PatternEntry", *, bounded: bool = False) -> str:
    """The regex source of one entry; `bounded` keeps a phrase from matching inside a word."""
    if entry.mode == "regex":
        return entry.text
    escaped = re.escape(entry.text)
    return rf"(?<!\w){escaped}(?!\w)" if bounded else escaped


def joined(entries: Sequence["PatternEntry"], *, bounded: bool = False) -> str:
    return "|".join(f"(?:{entry_source(e, bounded=bounded)})" for e in entries)


def _unbounded_at(text: str, i: int) -> bool:
    return bool(_UNBOUNDED.match(text, i))


def _skip_class(text: str, i: int) -> int:
    """Index just past the character class starting at `text[i] == "["`."""
    j = i + 1
    if j < len(text) and text[j] == "^":
        j += 1
    if j < len(text) and text[j] == "]":
        j += 1
    while j < len(text) and text[j] != "]":
        j += 2 if text[j] == "\\" else 1
    return j + 1


def has_nested_unbounded(text: str) -> bool:
    """True for a group repeated without limit that itself repeats without limit."""
    stack: list[bool] = []  # per open group: does it contain an unbounded repeat?
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "[":
            i = _skip_class(text, i)
            continue
        if ch == "(":
            stack.append(False)
        elif ch == ")" and stack:
            inner = stack.pop()
            repeated = _unbounded_at(text, i + 1)
            if inner and repeated:
                return True
            if stack and (inner or repeated):
                stack[-1] = True
        elif stack and _unbounded_at(text, i):
            stack[-1] = True
        i += 1
    return False


def regex_problem(text: str) -> str | None:
    """Why this regex may not be stored, or None."""
    try:
        re.compile(text)
    except re.error as exc:
        return f"regex does not compile: {exc}"
    return SLOW if has_nested_unbounded(text) else None


def _yaml(name: str) -> Any:
    import yaml

    from src.core.config import ROOT_DIR

    with (ROOT_DIR / "config" / name).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def signal_descriptions() -> dict[str, str]:
    return {name: spec["description"] for name, spec in _yaml("detectors.yaml")["signals"].items()}


def supported_by() -> dict[str, list[str]]:
    """The actions that back each promise kind (fixed; config/validation.yaml)."""
    kinds = _yaml("validation.yaml")["promises"]["kinds"]
    return {kind: list(spec["supported_by"]) for kind, spec in kinds.items()}
