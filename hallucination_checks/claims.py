"""Hallucination detection (SRS Step 35).

Factual claims in generated text (reference numbers, money amounts, percentages, dates,
durations and policy IDs) must be traceable to the complaint, the order and customer
records, the retrieved policy passages or the rule matrix. Anything else is flagged.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime

from complaint_processing.preprocessing import (
    COMPLAINT_REF,
    DATE,
    ORDER_REF,
    TRANSACTION_REF,
    parse_amounts,
)

PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?%")
DURATION = re.compile(r"\b(\d+)\s(business |working )?(hours?|days?|weeks?)\b", re.IGNORECASE)
POLICY_CODE = re.compile(r"\b[A-Z]{2,6}-[A-Z]{2,5}-\d{2}\b")
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


@dataclass
class Sources:
    """Everything a generated claim may legitimately come from."""

    texts: list[str] = field(default_factory=list)  # complaint, policy passages
    refs: set[str] = field(default_factory=set)  # ORD-/TXN-/CMP-/CUST- references
    amounts: set[float] = field(default_factory=set)
    percents: set[float] = field(default_factory=set)
    dates: set[date] = field(default_factory=set)
    durations_hours: set[int] = field(default_factory=set)
    policy_codes: set[str] = field(default_factory=set)
    reference_date: date | None = None  # used to resolve dates written without a year

    def add_text(self, text: str) -> None:
        self.texts.append(text)
        self.refs.update(m.upper() for m in ORDER_REF.findall(text))
        self.refs.update(m.upper() for m in TRANSACTION_REF.findall(text))
        self.refs.update(m.upper() for m in COMPLAINT_REF.findall(text))
        self.amounts.update(parse_amounts(text))
        self.percents.update(float(p) for p in PERCENT.findall(text))
        self.policy_codes.update(POLICY_CODE.findall(text))
        for amount, _, unit in DURATION.findall(text):
            self.durations_hours.add(_hours(amount, unit))
        for raw in DATE.findall(text):
            parsed = parse_loose_date(raw, self.reference_date)
            if parsed:
                self.dates.add(parsed)


@dataclass(frozen=True)
class Claim:
    kind: str
    value: str


def _hours(amount: str, unit: str) -> int:
    return int(amount) * {"hour": 1, "day": 24, "week": 168}[unit.lower().rstrip("s")]


def parse_loose_date(raw: str, reference: date | None) -> date | None:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    match = re.match(r"(\d{1,2})(?:st|nd|rd|th)? ([a-z]+)(?: (\d{4}))?", raw, re.IGNORECASE)
    if match and match.group(2)[:3].lower() in MONTHS:
        year = int(match.group(3)) if match.group(3) else (reference or date.today()).year
        try:
            return date(year, MONTHS.index(match.group(2)[:3].lower()) + 1, int(match.group(1)))
        except ValueError:
            return None
    return None


def extract_claims(text: str, reference: date | None) -> list[Claim]:
    claims: list[Claim] = []
    for pattern in (ORDER_REF, TRANSACTION_REF, COMPLAINT_REF):
        claims += [Claim("reference", m.upper()) for m in pattern.findall(text)]
    claims += [Claim("amount", f"{a:.2f}") for a in parse_amounts(text)]
    claims += [Claim("percent", p) for p in PERCENT.findall(text)]
    claims += [Claim("duration", f"{a} {b or ''}{u}".strip()) for a, b, u in DURATION.findall(text)]
    claims += [Claim("policy", code) for code in POLICY_CODE.findall(text)]
    for raw in DATE.findall(text):
        parsed = parse_loose_date(raw, reference)
        if parsed:
            claims.append(Claim("date", parsed.isoformat()))
    return list(dict.fromkeys(claims))


def unsupported_claims(claims: Iterable[Claim], sources: Sources) -> list[Claim]:
    derived_amounts = {
        round(amount * pct / 100, 2) for amount in sources.amounts for pct in sources.percents
    }
    unsupported = []
    for claim in claims:
        if claim.kind == "reference":
            ok = claim.value in sources.refs
        elif claim.kind == "amount":
            value = float(claim.value)
            ok = any(abs(value - a) < 0.01 for a in sources.amounts | derived_amounts)
        elif claim.kind == "percent":
            ok = float(claim.value) in sources.percents
        elif claim.kind == "duration":
            amount, *_, unit = claim.value.split()
            ok = _hours(amount, unit) in sources.durations_hours
        elif claim.kind == "policy":
            ok = claim.value in sources.policy_codes
        elif claim.kind == "date":
            ok = date.fromisoformat(claim.value) in sources.dates
        else:
            ok = True
        if not ok:
            unsupported.append(claim)
    return unsupported
