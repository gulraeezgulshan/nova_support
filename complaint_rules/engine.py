"""Evaluate the Complaint Resolution Rule Matrix against a set of facts.

Two kinds of rules:
- **Resolution rules** belong to a category (and usually a subcategory). For each issue the
  most specific matching rule is chosen: subcategory match beats category-only, a rule with
  a condition beats one without, then the higher `rule_priority` wins.
- **Escalation rules** have no category. Every one whose condition holds applies, whatever
  the complaint is about. That is how a calmly written safety complaint, or one the GenAI
  model misclassified, is still escalated.

The decision takes the most severe urgency, priority and escalation level, and the union of
required/prohibited actions and policy references. When several departments are involved,
the most severe (routing severity order) is primary and the rest are supporting.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml

from complaint_rules.conditions import Condition, compile_condition
from src.core.config import ROOT_DIR

URGENCY_ORDER = ["Low", "Medium", "High", "Critical"]
PRIORITY_ORDER = ["P3", "P2", "P1", "P0"]  # ascending severity


@dataclass(frozen=True)
class RoutingConfig:
    severity_order: list[str]
    category_default_department: dict[str, str]
    fallback_department: str


@lru_cache
def routing_config() -> RoutingConfig:
    with (ROOT_DIR / "routing_rules" / "routing.yaml").open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return RoutingConfig(
        data["severity_order"], data["category_default_department"], data["fallback_department"]
    )


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    rule_type: str  # resolution | escalation
    description: str
    category: str | None
    subcategory: str | None
    condition: Condition
    department: str | None
    supporting_departments: tuple[str, ...]
    urgency: str | None
    priority: str | None
    escalation_level: int
    required_actions: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    policy_refs: tuple[str, ...]
    follow_up_type: str | None
    follow_up_hours: int | None
    rule_priority: int

    @classmethod
    def from_record(cls, record: Any) -> "RuleSpec":
        """Build from a `Rule` ORM row or any object with the same attributes."""
        return cls(
            rule_id=record.rule_id,
            rule_type=str(record.rule_type),
            description=record.description,
            category=record.category or None,
            subcategory=record.subcategory or None,
            condition=compile_condition(record.condition or ""),
            department=record.department or None,
            supporting_departments=tuple(record.supporting_departments or ()),
            urgency=record.urgency or None,
            priority=record.priority or None,
            escalation_level=int(record.escalation_level or 0),
            required_actions=tuple(record.required_actions or ()),
            prohibited_actions=tuple(record.prohibited_actions or ()),
            policy_refs=tuple(record.policy_refs or ()),
            follow_up_type=record.follow_up_type or None,
            follow_up_hours=record.follow_up_hours,
            rule_priority=int(record.rule_priority or 0),
        )

    def specificity(self) -> tuple[int, int, int]:
        return (
            1 if self.subcategory else 0,
            1 if self.condition.tree is not None else 0,
            self.rule_priority,
        )


@dataclass(frozen=True)
class Issue:
    category: str
    subcategory: str | None


@dataclass
class Decision:
    """Expected handling according to the rule matrix (Python ground truth)."""

    department: str
    supporting_departments: list[str]
    urgency: str
    priority: str
    escalation_level: int
    required_actions: list[str]
    prohibited_actions: list[str]
    policy_refs: list[str]
    follow_up_type: str | None
    follow_up_hours: int | None
    resolution_rules: list[str] = field(default_factory=list)
    escalation_rules: list[str] = field(default_factory=list)
    unmatched_issues: list[str] = field(default_factory=list)

    @property
    def matched_rules(self) -> list[str]:
        return self.resolution_rules + self.escalation_rules


def select_resolution_rule(
    rules: Iterable[RuleSpec], issue: Issue, facts: Mapping[str, Any]
) -> RuleSpec | None:
    issue_facts = {**facts, "category": issue.category, "subcategory": issue.subcategory}
    candidates = [
        rule
        for rule in rules
        if rule.rule_type == "resolution"
        and rule.category == issue.category
        and (rule.subcategory is None or rule.subcategory == issue.subcategory)
        and rule.condition.evaluate(issue_facts)
    ]
    return max(candidates, key=RuleSpec.specificity, default=None)


def decide(
    rules: Sequence[RuleSpec], issues: Sequence[Issue], facts: Mapping[str, Any]
) -> Decision:
    """Apply the rule matrix to one complaint. `issues[0]` is the primary issue."""
    if not issues:
        raise ValueError("At least one issue (the primary one) is required")
    routing = routing_config()
    facts = {
        **facts,
        "category": issues[0].category,
        "subcategory": issues[0].subcategory,
        "issue_categories": [i.category for i in issues],
    }

    applied: list[RuleSpec] = []
    resolution_ids: list[str] = []
    unmatched: list[str] = []
    departments: list[str] = []
    for issue in issues:
        rule = select_resolution_rule(rules, issue, facts)
        if rule is None:
            unmatched.append(f"{issue.category}/{issue.subcategory or '-'}")
            departments.append(
                routing.category_default_department.get(issue.category, routing.fallback_department)
            )
            continue
        applied.append(rule)
        resolution_ids.append(rule.rule_id)
        if rule.department:
            departments.append(rule.department)

    escalations = [
        rule for rule in rules if rule.rule_type == "escalation" and rule.condition.evaluate(facts)
    ]
    applied.extend(escalations)
    departments.extend(rule.department for rule in escalations if rule.department)

    primary = _most_severe_department(departments, routing) or routing.fallback_department
    supporting = {d for d in departments if d != primary}
    for rule in applied:
        supporting.update(d for d in rule.supporting_departments if d != primary)

    urgencies = [r.urgency for r in applied if r.urgency in URGENCY_ORDER]
    priorities = [r.priority for r in applied if r.priority in PRIORITY_ORDER]
    follow_ups = [r for r in applied if r.follow_up_type]
    earliest_follow_up = min(follow_ups, key=lambda r: r.follow_up_hours or 10_000, default=None)

    return Decision(
        department=primary,
        supporting_departments=_ordered(supporting, routing.severity_order),
        urgency=max(urgencies, key=URGENCY_ORDER.index, default="Medium"),
        priority=max(priorities, key=PRIORITY_ORDER.index, default="P2"),
        escalation_level=max((r.escalation_level for r in applied), default=0),
        required_actions=_union(r.required_actions for r in applied),
        prohibited_actions=_union(r.prohibited_actions for r in applied),
        policy_refs=_union(r.policy_refs for r in applied),
        follow_up_type=earliest_follow_up.follow_up_type if earliest_follow_up else None,
        follow_up_hours=earliest_follow_up.follow_up_hours if earliest_follow_up else None,
        resolution_rules=resolution_ids,
        escalation_rules=[r.rule_id for r in escalations],
        unmatched_issues=unmatched,
    )


def _most_severe_department(departments: list[str], routing: RoutingConfig) -> str | None:
    if not departments:
        return None
    order = routing.severity_order
    return min(departments, key=lambda d: order.index(d) if d in order else len(order))


def _ordered(departments: set[str], order: list[str]) -> list[str]:
    return sorted(departments, key=lambda d: (order.index(d) if d in order else len(order), d))


def _union(groups: Iterable[Iterable[str]]) -> list[str]:
    seen: dict[str, None] = {}
    for group in groups:
        for item in group:
            seen.setdefault(item, None)
    return list(seen)
