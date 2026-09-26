"""Complaint pre-processing (SRS Step 11): character normalisation, sanitisation,
whitespace normalisation, metadata/entity extraction and duplicate hashing.

The original wording is kept (sanitised), because it is evidence; a separate lower-cased
form is used for matching and duplicate detection.
"""

import hashlib
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any

# Zero-width and bidirectional-control characters can hide instructions from human readers.
INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

ORDER_REF = re.compile(r"\bORD-\d{6}\b", re.IGNORECASE)
TRANSACTION_REF = re.compile(r"\bTXN-[A-Z0-9]{8,12}\b", re.IGNORECASE)
COMPLAINT_REF = re.compile(r"\bCMP-\d{6}\b", re.IGNORECASE)
_NUMBER = r"(?<![\w-])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?(?![\d,]*\d)"
AMOUNT = re.compile(
    rf"(?:(?:USD|US\$|\$)\s?{_NUMBER})|(?:{_NUMBER}\s?(?:USD|dollars?)\b)", re.IGNORECASE
)
DATE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}(?:st|nd|rd|th)? "
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?: \d{4})?)\b",
    re.IGNORECASE,
)
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")


def sanitize_text(text: str) -> str:
    """NFKC-normalise, drop invisible/control characters, tidy whitespace (keep paragraphs)."""
    text = unicodedata.normalize("NFKC", text or "")
    text = INVISIBLE.sub("", CONTROL.sub("", text))
    lines = [" ".join(line.split()) for line in text.replace("\r\n", "\n").split("\n")]
    text = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def normalize_for_matching(text: str) -> str:
    """Lower-case, letters/digits only: 'Refund NOT received!!' -> 'refund not received'."""
    return " ".join(re.sub(r"[^\w\s-]", " ", sanitize_text(text).lower()).split())


def content_hash(title: str, description: str) -> str:
    return hashlib.sha256(normalize_for_matching(f"{title} {description}").encode()).hexdigest()


def _unique_upper(matches: list[str]) -> list[str]:
    return list(dict.fromkeys(m.upper() for m in matches))


def parse_amounts(text: str) -> list[float]:
    amounts: list[float] = []
    for match in AMOUNT.finditer(text):
        whole, cents = (match.group(1), match.group(2)) if match.group(1) else match.group(3, 4)
        raw = whole.replace(",", "") + (f".{cents}" if cents else "")
        try:
            amounts.append(float(Decimal(raw)))
        except InvalidOperation:
            continue
    return amounts


def extract_entities(text: str) -> dict[str, Any]:
    """Deterministic entity extraction; the GenAI pipeline extracts entities independently."""
    return {
        "order_refs": _unique_upper(ORDER_REF.findall(text)),
        "transaction_refs": _unique_upper(TRANSACTION_REF.findall(text)),
        "complaint_refs": _unique_upper(COMPLAINT_REF.findall(text)),
        "amounts": parse_amounts(text),
        "dates": list(dict.fromkeys(DATE.findall(text))),
        "emails": list(dict.fromkeys(EMAIL.findall(text))),
    }
