"""Load, validate, store and export the Complaint Resolution Rule Matrix.

The CSV files are the reviewable source (`complaint_rules/rule_matrix.csv`,
`escalation_rules/escalation_rules.csv`); the `rules` table is the runtime copy that
administrators can change. Every row is validated before it is stored: known departments,
action codes, urgency/priority values, a condition that compiles, and well-formed policy
references such as `DEL-POL-04#5.2`.
"""

import csv
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from complaint_rules.conditions import ConditionError, compile_condition
from complaint_rules.engine import PRIORITY_ORDER, URGENCY_ORDER, RuleSpec
from database.models import Rule, RuleType
from src.core.config import ROOT_DIR
from src.core.domain import actions, analysis_config

RESOLUTION_CSV = ROOT_DIR / "complaint_rules" / "rule_matrix.csv"
ESCALATION_CSV = ROOT_DIR / "escalation_rules" / "escalation_rules.csv"
POLICY_REF = re.compile(r"^[A-Z]{2,6}(-[A-Z0-9]{2,8}){1,3}#\d+(\.\d+)*$")
FOLLOW_UP = re.compile(r"^([A-Z_]+)@(\d+)$")

EXPORT_COLUMNS = [
    "rule_id", "rule_type", "category", "subcategory", "condition", "department",
    "supporting_departments", "urgency", "priority", "escalation_level", "required_actions",
    "prohibited_actions", "policy_refs", "follow_up", "rule_priority", "is_active", "description",
]  # fmt: skip


class RuleMatrixError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class RuleRecord(BaseModel):
    rule_id: str
    rule_type: RuleType
    description: str
    category: str | None = None
    subcategory: str | None = None
    condition: str = ""
    department: str | None = None
    supporting_departments: list[str] = []
    urgency: str | None = None
    priority: str | None = None
    escalation_level: int = 0
    required_actions: list[str] = []
    prohibited_actions: list[str] = []
    policy_refs: list[str] = []
    follow_up_type: str | None = None
    follow_up_hours: int | None = None
    rule_priority: int = 50
    is_active: bool = True

    @field_validator("rule_id")
    @classmethod
    def _rule_id(cls, value: str) -> str:
        if not re.match(r"^[A-Z]{3}-\d{3}$", value):
            raise ValueError("must look like DEL-003")
        return value

    @field_validator("condition")
    @classmethod
    def _condition(cls, value: str) -> str:
        try:
            return compile_condition(value).source
        except ConditionError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("urgency")
    @classmethod
    def _urgency(cls, value: str | None) -> str | None:
        if value is not None and value not in URGENCY_ORDER:
            raise ValueError(f"must be one of {URGENCY_ORDER}")
        return value

    @field_validator("priority")
    @classmethod
    def _priority(cls, value: str | None) -> str | None:
        if value is not None and value not in PRIORITY_ORDER:
            raise ValueError(f"must be one of {PRIORITY_ORDER}")
        return value

    @field_validator("escalation_level")
    @classmethod
    def _level(cls, value: int) -> int:
        levels = [lvl.level for lvl in analysis_config().escalation_levels]
        if value not in levels:
            raise ValueError(f"must be one of {levels}")
        return value

    @field_validator("required_actions", "prohibited_actions")
    @classmethod
    def _actions(cls, value: list[str]) -> list[str]:
        unknown = [code for code in value if code not in actions()]
        if unknown:
            raise ValueError(f"unknown action code(s): {', '.join(unknown)}")
        return value

    @field_validator("policy_refs")
    @classmethod
    def _policy_refs(cls, value: list[str]) -> list[str]:
        bad = [ref for ref in value if not POLICY_REF.match(ref)]
        if bad:
            raise ValueError(f"policy references must look like DEL-POL-04#5.2: {bad}")
        return value

    @field_validator("follow_up_type")
    @classmethod
    def _follow_up(cls, value: str | None) -> str | None:
        if value is not None and value not in analysis_config().follow_up_types:
            raise ValueError(f"unknown follow-up type {value}")
        return value

    def check_references(self, departments: set[str], categories: dict[str, set[str]]) -> None:
        """Checks that need the live taxonomy (departments and categories)."""
        errors = []
        for dept in filter(None, [self.department, *self.supporting_departments]):
            if dept not in departments:
                errors.append(f"unknown department {dept}")
        if self.rule_type == RuleType.RESOLUTION:
            if not self.category:
                errors.append("resolution rules need a category")
            elif self.category not in categories:
                errors.append(f"unknown category {self.category}")
            elif self.subcategory and self.subcategory not in categories[self.category]:
                errors.append(f"{self.subcategory} is not a subcategory of {self.category}")
        if errors:
            raise RuleMatrixError([f"{self.rule_id}: {e}" for e in errors])


def _split(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(";") if item.strip()]


def parse_row(row: dict[str, str], rule_type: RuleType) -> RuleRecord:
    follow_up_type, follow_up_hours = None, None
    if row.get("follow_up"):
        match = FOLLOW_UP.match(row["follow_up"].strip())
        if not match:
            raise ValueError(f"follow_up must look like TYPE@48, got {row['follow_up']!r}")
        follow_up_type, follow_up_hours = match.group(1), int(match.group(2))
    return RuleRecord(
        rule_id=row["rule_id"].strip(),
        rule_type=rule_type,
        description=row.get("description", "").strip(),
        category=(row.get("category") or "").strip() or None,
        subcategory=(row.get("subcategory") or "").strip() or None,
        condition=(row.get("condition") or "").strip(),
        department=(row.get("department") or "").strip() or None,
        supporting_departments=_split(row.get("supporting_departments")),
        urgency=(row.get("urgency") or "").strip() or None,
        priority=(row.get("priority") or "").strip() or None,
        escalation_level=int(row.get("escalation_level") or 0),
        required_actions=_split(row.get("required_actions")),
        prohibited_actions=_split(row.get("prohibited_actions")),
        policy_refs=_split(row.get("policy_refs")),
        follow_up_type=follow_up_type,
        follow_up_hours=follow_up_hours,
        rule_priority=int(row.get("rule_priority") or 50),
        is_active=(row.get("is_active") or "true").strip().lower() != "false",
    )


def read_csv(path: Path, rule_type: RuleType) -> list[RuleRecord]:
    records, errors = [], []
    with path.open(encoding="utf-8", newline="") as handle:
        for line, row in enumerate(csv.DictReader(handle), start=2):
            try:
                records.append(parse_row(row, rule_type))
            except (ValidationError, ValueError) as exc:
                errors.append(f"{path.name} line {line} ({row.get('rule_id')}): {exc}")
    ids = [r.rule_id for r in records]
    errors += [f"duplicate rule_id {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    if errors:
        raise RuleMatrixError(errors)
    return records


def read_default_matrix() -> list[RuleRecord]:
    return read_csv(RESOLUTION_CSV, RuleType.RESOLUTION) + read_csv(
        ESCALATION_CSV, RuleType.ESCALATION
    )


def apply_record(rule: Rule, record: RuleRecord) -> bool:
    """Copy a validated record onto a row. Returns True when something changed."""
    changed = False
    for key, value in record.model_dump().items():
        if getattr(rule, key, None) != value:
            setattr(rule, key, value)
            changed = True
    return changed


def sync_rules(db: Session, records: Iterable[RuleRecord]) -> dict[str, int]:
    """Upsert rules by rule_id; changed rules get a new version number."""
    counts = {"created": 0, "updated": 0, "unchanged": 0}
    existing = {r.rule_id: r for r in db.scalars(select(Rule)).all()}
    for record in records:
        rule = existing.get(record.rule_id)
        if rule is None:
            rule = Rule(version=1)
            apply_record(rule, record)
            db.add(rule)
            counts["created"] += 1
        elif apply_record(rule, record):
            rule.version += 1
            counts["updated"] += 1
        else:
            counts["unchanged"] += 1
    db.flush()
    return counts


def to_specs(rules: Iterable[Rule]) -> list[RuleSpec]:
    return [RuleSpec.from_record(rule) for rule in rules if rule.is_active]


def load_specs(db: Session) -> list[RuleSpec]:
    return to_specs(db.scalars(select(Rule).order_by(Rule.rule_id)).all())


async def load_specs_async(db: AsyncSession) -> list[RuleSpec]:
    return to_specs((await db.scalars(select(Rule).order_by(Rule.rule_id))).all())


def export_rows(rules: Sequence[Rule]) -> list[dict[str, Any]]:
    return [
        {
            "rule_id": r.rule_id,
            "rule_type": r.rule_type,
            "category": r.category or "",
            "subcategory": r.subcategory or "",
            "condition": r.condition,
            "department": r.department or "",
            "supporting_departments": ";".join(r.supporting_departments),
            "urgency": r.urgency or "",
            "priority": r.priority or "",
            "escalation_level": r.escalation_level,
            "required_actions": ";".join(r.required_actions),
            "prohibited_actions": ";".join(r.prohibited_actions),
            "policy_refs": ";".join(r.policy_refs),
            "follow_up": f"{r.follow_up_type}@{r.follow_up_hours}" if r.follow_up_type else "",
            "rule_priority": r.rule_priority,
            "is_active": str(r.is_active).lower(),
            "description": r.description,
        }
        for r in rules
    ]
