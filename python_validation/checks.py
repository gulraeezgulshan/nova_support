"""Python Ground-Truth Validation Pipeline (Pipeline 2): the checks.

`validate()` compares a GenAI analysis with what Python derives on its own: an independent
keyword classification, the Complaint Resolution Rule Matrix evaluated on Python-computed
facts, the active policy versions, and the traceable facts of the complaint. No GenAI API is
used to approve anything.

Outcome:
- VERIFIED: every check passed or only warned.
- CORRECTED: Python enforced rule values it can fix safely (raise priority, urgency or
  escalation to the rule minimum, add mandatory actions, drop prohibited steps).
- NEEDS_REVIEW: a human must decide (category or routing disagreement, unsupported promise,
  hallucinated fact, unsupported compensation, outdated policy, sensitive complaint, missing
  GenAI output).
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from complaint_rules.engine import PRIORITY_ORDER, URGENCY_ORDER, Decision, Issue, RuleSpec, decide
from genai_pipeline.validation import parse_and_validate
from genai_pipeline.vocabulary import Vocabulary
from hallucination_checks.claims import Sources, extract_claims, unsupported_claims
from hallucination_checks.promises import find_promises, unsupported_promises
from python_validation.classifier import Classification, classify
from python_validation.types import (
    CheckResult,
    CheckStatus,
    Severity,
    Verdict,
    validation_config,
)
from schemas.complaint_analysis import ComplaintAnalysis

PASS, WARN, FAIL, SKIP = CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL, CheckStatus.SKIP
CRITICAL, MAJOR, MINOR = Severity.CRITICAL, Severity.MAJOR, Severity.MINOR


@dataclass
class PolicyPassage:
    chunk_code: str
    doc_code: str
    doc_type: str
    precedence: int
    version: str
    content: str
    status: str  # current status of the document version (active, superseded, ...)


@dataclass
class ValidationInput:
    complaint_ref: str
    text: str  # title + description + requested resolution
    signals: dict[str, Any]
    facts: dict[str, Any]
    taxonomy: dict[str, list[str]]
    vocab: Vocabulary
    rules: list[RuleSpec]
    analysis: ComplaintAnalysis | None
    passages: list[PolicyPassage]
    record_texts: list[str] = field(default_factory=list)  # order/customer/history facts
    reference_date: date | None = None
    sla_hours: dict[str, tuple[float, float]] = field(default_factory=dict)  # P -> (first, res)


@dataclass
class ValidationOutcome:
    verdict: Verdict
    score: float
    checks: list[CheckResult]
    classification: Classification
    decision: Decision
    python_issues: list[Issue]
    classification_source: str  # python | genai_fallback | none
    final: dict[str, Any]
    corrections: list[str]
    review_reasons: list[str]

    def python_expected(self) -> dict[str, Any]:
        primary = self.python_issues[0] if self.python_issues else None
        return {
            "category": primary.category if primary else None,
            "subcategory": primary.subcategory if primary else None,
            "secondary_issues": [f"{i.category}/{i.subcategory}" for i in self.python_issues[1:]],
            "classification_source": self.classification_source,
            "classifier": self.classification.to_dict(),
            "department": self.decision.department,
            "supporting_departments": self.decision.supporting_departments,
            "urgency": self.decision.urgency,
            "priority": self.decision.priority,
            "escalation_level": self.decision.escalation_level,
            "required_actions": self.decision.required_actions,
            "prohibited_actions": self.decision.prohibited_actions,
            "policy_refs": self.decision.policy_refs,
            "follow_up_type": self.decision.follow_up_type,
            "follow_up_hours": self.decision.follow_up_hours,
            "resolution_rules": self.decision.resolution_rules,
            "escalation_rules": self.decision.escalation_rules,
        }


def _python_issues(
    classification: Classification, analysis: ComplaintAnalysis | None
) -> tuple[list[Issue], str]:
    if classification.confidence == "confident" and classification.primary:
        issues = [Issue(classification.primary.category, classification.primary.subcategory)]
        issues += [Issue(c.category, c.subcategory) for c in classification.secondary]
        return issues, "python"
    if analysis is not None:  # Python cannot tell: use the GenAI classification, flagged
        issues = [Issue(analysis.primary_issue.category, analysis.primary_issue.subcategory)]
        issues += [Issue(i.category, i.subcategory) for i in analysis.secondary_issues]
        return issues, "genai_fallback"
    if classification.primary:
        return [
            Issue(classification.primary.category, classification.primary.subcategory)
        ], "python"
    return [Issue("UNCLASSIFIED", None)], "none"


def _escalation_level(analysis: ComplaintAnalysis, vocab: Vocabulary) -> int:
    codes = list(vocab.escalation_levels)
    return codes.index(analysis.escalation.level) if analysis.escalation.level in codes else 0


def validate(inp: ValidationInput) -> ValidationOutcome:
    cfg = validation_config()
    classification = classify(inp.text, inp.signals, inp.taxonomy)
    a = inp.analysis
    python_issues, source = _python_issues(classification, a)
    decision = decide(inp.rules, python_issues, inp.facts)
    checks: list[CheckResult] = []

    if a is None:
        checks.append(
            CheckResult(
                "schema",
                "GenAI JSON schema",
                FAIL,
                CRITICAL,
                "No valid GenAI output is available; the rule-matrix decision is applied "
                "on its own.",
            )
        )
        return _finish(inp, checks, classification, decision, python_issues, source, cfg)

    retrieved = {p.chunk_code: p.doc_code for p in inp.passages}
    _, schema_errors = parse_and_validate(
        json.dumps(a.model_dump(mode="json")), inp.vocab, retrieved
    )
    checks.append(
        CheckResult(
            "schema",
            "GenAI JSON schema",
            FAIL if schema_errors else PASS,
            CRITICAL,
            "; ".join(schema_errors) or "Required fields, types and codes are valid.",
        )
    )

    checks += [
        _check_category(a, classification),
        _check_subcategory(a, classification),
        _check_department(a, decision),
        _check_supporting(a, decision),
        _check_scale("urgency", "Urgency", a.urgency, decision.urgency, URGENCY_ORDER, decision),
        _check_scale(
            "priority",
            "Priority",
            a.priority,
            decision.priority,
            PRIORITY_ORDER,
            decision,
        ),
        _check_escalation(a, decision, inp.vocab),
        _check_required_actions(a, decision, inp.vocab, cfg),
        _check_prohibited_actions(a, decision, cfg),
        _check_compensation(a, decision, inp.facts, cfg),
        _check_policies(a, decision, inp.passages),
        _check_promises(a, decision, inp, cfg),
        _check_hallucinations(a, decision, inp),
        _check_contradictions(a, inp.vocab),
        _check_missing_information(a, inp.facts, cfg),
        _check_injection(a, inp.signals),
        _check_follow_up(a, decision),
    ]
    return _finish(inp, checks, classification, decision, python_issues, source, cfg)


# ---------------------------------------------------------------- individual checks


def _check_category(a: ComplaintAnalysis, c: Classification) -> CheckResult:
    genai = a.primary_issue.category
    genai_all = {genai} | {i.category for i in a.secondary_issues}
    if c.confidence != "confident" or c.primary is None:
        return CheckResult(
            "category",
            "Complaint category",
            SKIP,
            MAJOR,
            "Python found too little evidence to classify independently; the GenAI category "
            "is accepted provisionally.",
            actual=genai,
        )
    expected, evidence = c.primary.category, list(c.primary.evidence)
    if genai == expected:
        return CheckResult(
            "category",
            "Complaint category",
            PASS,
            MAJOR,
            "GenAI and Python agree.",
            expected,
            genai,
            evidence,
        )
    if genai in c.categories or expected in genai_all:
        return CheckResult(
            "category",
            "Complaint category",
            WARN,
            MAJOR,
            f"Both found the same issues but disagree on which is primary ({genai} vs {expected}).",
            expected,
            genai,
            evidence,
        )
    return CheckResult(
        "category",
        "Complaint category",
        FAIL,
        MAJOR,
        f"GenAI chose {genai}; Python's evidence points to {expected}.",
        expected,
        genai,
        evidence,
    )


def _check_subcategory(a: ComplaintAnalysis, c: Classification) -> CheckResult:
    genai = a.primary_issue.subcategory
    if c.confidence != "confident" or c.primary is None:
        return CheckResult(
            "subcategory",
            "Subcategory",
            SKIP,
            MINOR,
            "Not independently determinable.",
            actual=genai,
        )
    strong = {cand.subcategory for cand in c.candidates if cand.score >= 3}
    if genai == c.primary.subcategory or genai in strong:
        return CheckResult(
            "subcategory",
            "Subcategory",
            PASS,
            MINOR,
            "Consistent with Python.",
            c.primary.subcategory,
            genai,
        )
    return CheckResult(
        "subcategory",
        "Subcategory",
        WARN,
        MINOR,
        f"Python expected {c.primary.subcategory}.",
        c.primary.subcategory,
        genai,
        list(c.primary.evidence),
    )


def _check_department(a: ComplaintAnalysis, d: Decision) -> CheckResult:
    rules = ", ".join(d.matched_rules) or "category default"
    if a.department == d.department:
        return CheckResult(
            "department",
            "Department routing",
            PASS,
            MAJOR,
            f"Matches the rule matrix ({rules}).",
            d.department,
            a.department,
        )
    if a.department in d.supporting_departments:
        return CheckResult(
            "department",
            "Department routing",
            WARN,
            MAJOR,
            f"{a.department} is involved, but the routing rules make {d.department} the owner "
            "(most severe issue).",
            d.department,
            a.department,
            [rules],
            correctable=True,
        )
    return CheckResult(
        "department",
        "Department routing",
        FAIL,
        MAJOR,
        f"Rule matrix routes to {d.department} ({rules}).",
        d.department,
        a.department,
        [rules],
    )


def _check_supporting(a: ComplaintAnalysis, d: Decision) -> CheckResult:
    involved = {a.department, *a.supporting_departments}
    missing = [dept for dept in d.supporting_departments if dept not in involved]
    if not missing:
        return CheckResult(
            "supporting_departments",
            "Multi-department routing",
            PASS,
            MINOR,
            "All required departments are involved.",
            d.supporting_departments,
            a.supporting_departments,
        )
    return CheckResult(
        "supporting_departments",
        "Multi-department routing",
        FAIL,
        MINOR,
        f"Missing supporting department(s): {', '.join(missing)}.",
        d.supporting_departments,
        a.supporting_departments,
        correctable=True,
    )


def _check_scale(
    code: str, name: str, genai: str, expected: str, order: list[str], d: Decision
) -> CheckResult:
    """`order` runs from least to most severe."""
    g = order.index(genai) if genai in order else -1
    e = order.index(expected)
    severity = CRITICAL if e >= len(order) - 2 else MAJOR
    if g == e:
        return CheckResult(code, name, PASS, severity, "Matches the rule matrix.", expected, genai)
    if g < e:
        return CheckResult(
            code,
            name,
            FAIL,
            severity,
            f"GenAI set {genai}; the rules require at least {expected} "
            f"({', '.join(d.escalation_rules or d.resolution_rules)}).",
            expected,
            genai,
            correctable=True,
        )
    return CheckResult(
        code,
        name,
        WARN,
        MINOR,
        f"GenAI set {genai}, more urgent than the rules require ({expected}). "
        "Urgency must reflect business risk, not tone.",
        expected,
        genai,
    )


def _check_escalation(a: ComplaintAnalysis, d: Decision, vocab: Vocabulary) -> CheckResult:
    genai = _escalation_level(a, vocab)
    rules = ", ".join(d.escalation_rules) or "resolution rules"
    if genai == d.escalation_level:
        return CheckResult(
            "escalation",
            "Mandatory escalation",
            PASS,
            CRITICAL,
            "Matches the escalation rules.",
            d.escalation_level,
            genai,
        )
    if genai < d.escalation_level:
        return CheckResult(
            "escalation",
            "Mandatory escalation",
            FAIL,
            CRITICAL,
            f"Escalation missed: rules require level {d.escalation_level} ({rules}); GenAI "
            f"chose {genai}. Python enforces the rule.",
            d.escalation_level,
            genai,
            [rules],
            correctable=True,
        )
    return CheckResult(
        "escalation",
        "Mandatory escalation",
        WARN,
        MINOR,
        f"GenAI escalated higher ({genai}) than the rules require ({d.escalation_level}).",
        d.escalation_level,
        genai,
    )


def _check_required_actions(
    a: ComplaintAnalysis, d: Decision, vocab: Vocabulary, cfg: dict[str, Any]
) -> CheckResult:
    present = {step.action_code for step in a.resolution_steps}
    level = _escalation_level(a, vocab)
    escalation_levels: dict[str, int] = cfg["escalation_action_levels"]
    missing = [
        code
        for code in d.required_actions
        if code not in present
        and not (code in escalation_levels and level >= escalation_levels[code])
    ]
    if not missing:
        return CheckResult(
            "required_actions",
            "Mandatory actions",
            PASS,
            MAJOR,
            "Every action the rules require is present.",
            d.required_actions,
            sorted(present),
        )
    return CheckResult(
        "required_actions",
        "Mandatory actions",
        FAIL,
        MAJOR,
        f"Missing mandatory action(s): {', '.join(missing)}. Python adds them to the plan.",
        d.required_actions,
        sorted(present),
        missing,
        correctable=True,
    )


def blocked_actions(d: Decision, cfg: dict[str, Any]) -> list[str]:
    """What the rules prohibit for this complaint plus what is never allowed at all."""
    return list(dict.fromkeys([*d.prohibited_actions, *cfg.get("never_allowed_actions", [])]))


def _check_prohibited_actions(
    a: ComplaintAnalysis, d: Decision, cfg: dict[str, Any]
) -> CheckResult:
    blocked = blocked_actions(d, cfg)
    used = [s.action_code for s in a.resolution_steps if s.action_code in blocked]
    if not used:
        return CheckResult(
            "prohibited_actions",
            "Prohibited actions",
            PASS,
            CRITICAL,
            "No prohibited action is proposed.",
            d.prohibited_actions,
        )
    return CheckResult(
        "prohibited_actions",
        "Prohibited actions",
        FAIL,
        CRITICAL,
        f"Prohibited step(s) proposed: {', '.join(used)}. Python removes them.",
        d.prohibited_actions,
        used,
        used,
        correctable=True,
    )


def _check_compensation(
    a: ComplaintAnalysis, d: Decision, facts: dict[str, Any], cfg: dict[str, Any]
) -> CheckResult:
    comp = a.compensation
    if not comp.offered or comp.type == "none":
        return CheckResult(
            "compensation", "Compensation eligibility", PASS, CRITICAL, "No compensation offered."
        )
    rule = cfg["compensation"].get(comp.type)
    if rule is None or not set(rule["requires_any"]) & set(d.required_actions):
        return CheckResult(
            "compensation",
            "Compensation eligibility",
            FAIL,
            CRITICAL,
            f"{comp.type} is not supported by the rules for this complaint "
            f"(rules require: {', '.join(d.required_actions) or 'nothing'}).",
            actual=comp.model_dump(),
        )
    order_amount = facts.get("order_amount")
    limits = []
    if comp.amount is not None and "max_amount" in rule:
        limits.append(float(rule["max_amount"]))
    if comp.amount is not None and "max_pct_of_order" in rule and order_amount:
        limits.append(round(order_amount * rule["max_pct_of_order"] / 100, 2))
    if comp.amount is not None and limits and comp.amount > min(limits) + 0.01:
        return CheckResult(
            "compensation",
            "Compensation eligibility",
            FAIL,
            CRITICAL,
            f"Offered {comp.amount:.2f} exceeds the policy limit of {min(limits):.2f}.",
            min(limits),
            comp.amount,
        )
    return CheckResult(
        "compensation",
        "Compensation eligibility",
        PASS,
        CRITICAL,
        f"{comp.type} is allowed by the rules and within limits.",
    )


def _check_policies(
    a: ComplaintAnalysis, d: Decision, passages: list[PolicyPassage]
) -> CheckResult:
    by_code = {p.chunk_code: p for p in passages}
    cited = [by_code[r.chunk_code] for r in a.policy_references if r.chunk_code in by_code]
    applicable = [
        by_code[r.chunk_code]
        for r in a.policy_references
        if r.chunk_code in by_code and r.applicability in ("applicable", "conditionally_applicable")
    ]
    outdated = [p.chunk_code for p in cited if p.status != "active"]
    if outdated:
        return CheckResult(
            "policy",
            "Policy version and applicability",
            FAIL,
            MAJOR,
            f"Cites policy that is no longer active: {', '.join(outdated)}.",
            actual=outdated,
        )
    if not cited:
        return CheckResult(
            "policy",
            "Policy version and applicability",
            FAIL,
            MAJOR,
            "No approved policy passage supports the recommendation.",
            expected=d.policy_refs,
        )
    governing = {ref.split("#")[0] for ref in d.policy_refs}
    weaker = [p for p in applicable if p.precedence > 3]
    stronger = [p for p in passages if p.precedence <= 2]
    if weaker and stronger and not any(p.precedence <= 2 for p in applicable):
        return CheckResult(
            "policy",
            "Policy version and applicability",
            WARN,
            MAJOR,
            f"Relies on lower-precedence sources ({', '.join(p.doc_code for p in weaker)}) while "
            f"a higher-precedence document was available ({stronger[0].doc_code}).",
            expected=sorted(governing),
            actual=[p.doc_code for p in applicable],
        )
    if governing and not governing & {p.doc_code for p in cited}:
        return CheckResult(
            "policy",
            "Policy version and applicability",
            WARN,
            MAJOR,
            f"The governing policy ({', '.join(sorted(governing))}) is not cited.",
            expected=sorted(governing),
            actual=[p.doc_code for p in cited],
        )
    return CheckResult(
        "policy",
        "Policy version and applicability",
        PASS,
        MAJOR,
        "Citations are active and include the governing policy.",
        sorted(governing),
        [p.chunk_code for p in cited],
    )


def _allowed_durations(d: Decision, inp: ValidationInput) -> set[int]:
    hours = {int(d.follow_up_hours)} if d.follow_up_hours else set()
    for first, resolution in inp.sla_hours.values():
        hours.update({int(first), int(resolution)})
    return hours


def _check_promises(
    a: ComplaintAnalysis, d: Decision, inp: ValidationInput, cfg: dict[str, Any]
) -> CheckResult:
    text = "\n".join(filter(None, [a.customer_response.body, a.follow_up.message]))
    promises = find_promises(text)
    policy_text = "\n".join(p.content for p in inp.passages)
    bad = unsupported_promises(
        promises, set(d.required_actions), _allowed_durations(d, inp), policy_text
    )
    if not bad:
        return CheckResult(
            "promises",
            "Unsupported promises",
            PASS,
            CRITICAL,
            f"{len(promises)} commitment(s) found, all supported.",
        )
    return CheckResult(
        "promises",
        "Unsupported promises",
        FAIL,
        CRITICAL,
        "The customer response promises something the rules or policies do not support.",
        actual=[f"{p.kind}: {p.detail}" for p in bad],
        evidence=[p.sentence for p in bad],
    )


def _check_hallucinations(a: ComplaintAnalysis, d: Decision, inp: ValidationInput) -> CheckResult:
    decision = d
    sources = Sources(reference_date=inp.reference_date)
    for text in [
        inp.text,
        inp.complaint_ref,
        *inp.record_texts,
        *(p.content for p in inp.passages),
    ]:
        sources.add_text(text)
    sources.policy_codes.update(p.doc_code for p in inp.passages)
    # Timelines from the SLA and the rule follow-up are legitimate sources too.
    sources.durations_hours.update(_allowed_durations(decision, inp))
    generated = "\n".join(
        filter(
            None,
            [
                a.customer_response.body,
                a.follow_up.message,
                *(s.description for s in a.resolution_steps),
                a.escalation.notes.summary if a.escalation.notes else None,
                *(a.escalation.notes.key_facts if a.escalation.notes else []),
            ],
        )
    )
    claims = extract_claims(generated, inp.reference_date)
    bad = unsupported_claims(claims, sources)
    if not bad:
        return CheckResult(
            "hallucination",
            "Traceable facts",
            PASS,
            MAJOR,
            f"{len(claims)} factual claim(s) traced to the complaint, records or policies.",
        )
    return CheckResult(
        "hallucination",
        "Traceable facts",
        FAIL,
        MAJOR,
        "Generated text contains facts that cannot be traced to the complaint, the records, "
        "the policies or the rule matrix.",
        actual=[f"{c.kind}: {c.value}" for c in bad],
    )


def _check_contradictions(a: ComplaintAnalysis, vocab: Vocabulary) -> CheckResult:
    problems = []
    escalating = [s.action_code for s in a.resolution_steps if s.action_code.startswith("ESCALATE")]
    if escalating and not a.escalation.required:
        problems.append(
            f"Steps escalate ({', '.join(escalating)}) but escalation is 'not required'."
        )
    if a.priority in ("P0", "P1") and a.urgency == "Low":
        problems.append(f"Priority {a.priority} contradicts Low urgency.")
    if a.priority == "P3" and a.urgency in ("High", "Critical"):
        problems.append(f"Priority P3 contradicts {a.urgency} urgency.")
    if a.missing_information and not a.clarification_questions:
        problems.append("Missing information is listed but no clarification question is asked.")
    if (
        a.compensation.offered
        and "REQUEST_MISSING_INFORMATION" in {s.action_code for s in a.resolution_steps}
        and a.missing_information
    ):
        problems.append("Compensation is offered while essential information is still missing.")
    if not problems:
        return CheckResult(
            "contradictions",
            "Contradictory instructions",
            PASS,
            MAJOR,
            "No internal contradictions.",
        )
    return CheckResult(
        "contradictions",
        "Contradictory instructions",
        FAIL,
        MAJOR,
        " ".join(problems),
        actual=problems,
    )


def _check_missing_information(
    a: ComplaintAnalysis, facts: dict[str, Any], cfg: dict[str, Any]
) -> CheckResult:
    needs_order = a.primary_issue.category in cfg["orders_required_for"]
    if needs_order and not facts.get("has_order"):
        if a.clarification_questions or a.missing_information:
            return CheckResult(
                "missing_information",
                "Missing information",
                PASS,
                MAJOR,
                "No order is linked and the GenAI asks for it instead of guessing.",
            )
        return CheckResult(
            "missing_information",
            "Missing information",
            FAIL,
            MAJOR,
            f"{a.primary_issue.category} complaints need an order, none is linked, and no "
            "clarification is requested.",
            correctable=True,
        )
    return CheckResult(
        "missing_information",
        "Missing information",
        PASS,
        MAJOR,
        "Required information is present.",
    )


def _check_injection(a: ComplaintAnalysis, signals: dict[str, Any]) -> CheckResult:
    if not signals.get("prompt_injection"):
        return CheckResult(
            "injection",
            "Prompt-injection handling",
            PASS,
            CRITICAL,
            "No injection attempt detected.",
        )
    if a.compensation.offered:
        return CheckResult(
            "injection",
            "Prompt-injection handling",
            FAIL,
            CRITICAL,
            "The complaint contains injected instructions and the GenAI offered compensation.",
            evidence=signals["prompt_injection"],
        )
    if not a.suspicious_instructions:
        return CheckResult(
            "injection",
            "Prompt-injection handling",
            WARN,
            CRITICAL,
            "Python detected injected instructions that the GenAI did not report.",
            evidence=signals["prompt_injection"],
        )
    return CheckResult(
        "injection",
        "Prompt-injection handling",
        PASS,
        CRITICAL,
        "Injected instructions were recognised and ignored.",
        evidence=a.suspicious_instructions,
    )


def _check_follow_up(a: ComplaintAnalysis, d: Decision) -> CheckResult:
    if not d.follow_up_type:
        return CheckResult(
            "follow_up", "Follow-up requirement", PASS, MINOR, "No follow-up required by the rules."
        )
    if not a.follow_up.required:
        return CheckResult(
            "follow_up",
            "Follow-up requirement",
            FAIL,
            MINOR,
            f"Rules require {d.follow_up_type} within {d.follow_up_hours} h.",
            f"{d.follow_up_type}@{d.follow_up_hours}",
            None,
            correctable=True,
        )
    if (
        a.follow_up.within_hours
        and d.follow_up_hours
        and a.follow_up.within_hours > d.follow_up_hours
    ):
        return CheckResult(
            "follow_up",
            "Follow-up requirement",
            WARN,
            MINOR,
            f"Follow-up in {a.follow_up.within_hours} h; rules require {d.follow_up_hours} h.",
            d.follow_up_hours,
            a.follow_up.within_hours,
            correctable=True,
        )
    return CheckResult(
        "follow_up", "Follow-up requirement", PASS, MINOR, "Follow-up planned as required."
    )


# ------------------------------------------------------------------ verdict and final


def score(checks: Iterable[CheckResult], weights: dict[str, int]) -> float:
    earned = total = 0.0
    for check in checks:
        if check.status == SKIP:
            continue
        weight = weights[check.severity]
        total += weight
        earned += weight if check.status == PASS else weight / 2 if check.status == WARN else 0
    return round(100 * earned / total, 1) if total else 0.0


def _more_severe(a: str, b: str, order: list[str]) -> str:
    return a if order.index(a) >= order.index(b) else b


def _finish(
    inp: ValidationInput,
    checks: list[CheckResult],
    classification: Classification,
    decision: Decision,
    python_issues: list[Issue],
    source: str,
    cfg: dict[str, Any],
) -> ValidationOutcome:
    a = inp.analysis
    corrections: list[str] = []
    reasons: list[str] = []
    for check in checks:
        if check.status == FAIL and not check.correctable:
            reasons.append(f"{check.name}: {check.message}")
        elif check.status == FAIL:
            corrections.append(f"{check.name}: {check.message}")

    if a is not None:
        urgency = _more_severe(a.urgency, decision.urgency, URGENCY_ORDER)
        priority = _more_severe(a.priority, decision.priority, PRIORITY_ORDER)
        escalation = max(_escalation_level(a, inp.vocab), decision.escalation_level)
        steps = [
            s.action_code
            for s in a.resolution_steps
            if s.action_code not in blocked_actions(decision, cfg)
        ]
        category: str = a.primary_issue.category
        subcategory: str | None = a.primary_issue.subcategory
        sentiment: str | None = a.sentiment
    else:
        urgency, priority, escalation = (
            decision.urgency,
            decision.priority,
            decision.escalation_level,
        )
        steps, sentiment = [], None
        primary = python_issues[0]
        category, subcategory = primary.category, primary.subcategory
    actions = list(dict.fromkeys(steps + decision.required_actions))
    if escalation >= cfg["always_review_escalation_level"]:
        reasons.append(
            f"Sensitive complaint (escalation level {escalation}) requires human review."
        )
    final = {
        "category": category,
        "subcategory": subcategory,
        "department": decision.department,
        "supporting_departments": decision.supporting_departments,
        "urgency": urgency,
        "priority": priority,
        "escalation_level": escalation,
        "sentiment": sentiment,
        "actions": [a for a in actions if a not in blocked_actions(decision, cfg)],
        "follow_up_type": decision.follow_up_type,
        "follow_up_hours": decision.follow_up_hours,
    }
    weights: dict[str, int] = cfg["score_weights"]
    total = score(checks, weights)
    if reasons:
        verdict = Verdict.NEEDS_REVIEW
    elif corrections:
        verdict = Verdict.CORRECTED
    elif total < cfg["verified_min_score"]:
        verdict = Verdict.NEEDS_REVIEW
        reasons.append(f"Verification score {total} is below {cfg['verified_min_score']}.")
    else:
        verdict = Verdict.VERIFIED
    return ValidationOutcome(
        verdict,
        total,
        checks,
        classification,
        decision,
        python_issues,
        source,
        final,
        corrections,
        reasons,
    )


def compare(
    outcome: ValidationOutcome,
    a: ComplaintAnalysis | None,
    vocab: Vocabulary,
    expected: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Field-by-field GenAI vs Python comparison (and dataset label when known)."""
    py = outcome.python_expected()
    genai = {
        "category": a.primary_issue.category if a else None,
        "subcategory": a.primary_issue.subcategory if a else None,
        "department": a.department if a else None,
        "urgency": a.urgency if a else None,
        "priority": a.priority if a else None,
        "escalation_level": _escalation_level(a, vocab) if a else None,
    }
    primary = outcome.classification.primary
    evidence = list(primary.evidence) if primary else []
    why = {
        "category": "Python keyword evidence: " + (", ".join(evidence) or "none"),
        "department": "Rules: " + (", ".join(outcome.decision.matched_rules) or "category default"),
        "escalation_level": "Escalation rules: "
        + (", ".join(outcome.decision.escalation_rules) or "none"),
    }
    rows = []
    for field_name, genai_value in genai.items():
        python_value = py[field_name]
        row = {
            "field": field_name,
            "genai": genai_value,
            "python": python_value,
            "match": genai_value == python_value,
            "explanation": ""
            if genai_value == python_value
            else why.get(field_name, "Rule matrix"),
        }
        if expected is not None and field_name in expected:
            row["expected"] = expected[field_name]
        rows.append(row)
    return rows
