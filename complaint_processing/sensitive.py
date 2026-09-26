"""Sensitive-data redaction at intake.

Customers sometimes paste card numbers, security codes, passwords or ID numbers into a
complaint. None of that is needed to resolve it, so it is removed before the complaint is
stored, embedded, logged or sent to the GenAI provider. The last four digits of a card are
kept, because agents use them to find a transaction.
"""

import re
from dataclasses import dataclass, field

CARD = re.compile(r"(?<![\w-])(?:\d[ -]?){12,18}\d(?![\w-])")
SECURITY_CODE = re.compile(r"\b(cvv2?|cvc2?|cid|security code)\s*(?:is|:|=|-)?\s*\d{3,4}\b", re.I)
PASSWORD = re.compile(
    r"\b(password|passcode)(\s*(?:is|was|:|=)\s*)(?:([\"'])(.{1,64}?)\3|(?!\[)(\S{3,64}))", re.I
)
ONE_TIME_CODE = re.compile(
    r"\b(pin|otp|one[- ]time (?:code|password)|verification code)(\s*(?:is|was|:|=|-)?\s*)"
    r"(\d{4,8})\b",
    re.I,
)
# Pakistani CNIC, US SSN and IBAN formats; order and complaint references are unaffected.
NATIONAL_ID = re.compile(r"\b(?:\d{5}-\d{7}-\d|\d{3}-\d{2}-\d{4})\b")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b")


def luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


@dataclass
class Redaction:
    text: str
    kinds: list[str] = field(default_factory=list)


def redact(text: str | None) -> Redaction:
    """Remove payment cards, security codes, passwords/PINs/OTPs and ID or bank numbers."""
    if not text:
        return Redaction(text or "")
    kinds: list[str] = []

    def card(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and luhn_valid(digits):
            kinds.append("payment card number")
            return f"[card ending {digits[-4:]}]"
        return match.group()

    def password(match: re.Match[str]) -> str:
        label = f"{match.group(1)}{match.group(2)}[redacted]"
        if match.group(3):  # quoted: "summer sky"
            kinds.append("password")
            return label
        token = match.group(5)
        value = token.rstrip(".,;:!?)")
        # "my password was changed" is a complaint, not a secret: only redact values that
        # look like one (containing a digit, symbol or an inner capital letter).
        if not re.search(r"[\d\W_]|.[A-Z]", value):
            return match.group()
        kinds.append("password")
        return label + token[len(value) :]

    def one_time_code(match: re.Match[str]) -> str:
        kinds.append("PIN or one-time code")
        return f"{match.group(1)}{match.group(2)}[redacted]"

    def code(match: re.Match[str]) -> str:
        kinds.append("card security code")
        return f"{match.group(1)} [redacted]"

    def national_id(_: re.Match[str]) -> str:
        kinds.append("national ID number")
        return "[ID number redacted]"

    def iban(_: re.Match[str]) -> str:
        kinds.append("bank account number")
        return "[bank account redacted]"

    text = CARD.sub(card, text)
    text = SECURITY_CODE.sub(code, text)
    text = PASSWORD.sub(password, text)
    text = ONE_TIME_CODE.sub(one_time_code, text)
    text = NATIONAL_ID.sub(national_id, text)
    text = IBAN.sub(iban, text)
    return Redaction(text, list(dict.fromkeys(kinds)))
