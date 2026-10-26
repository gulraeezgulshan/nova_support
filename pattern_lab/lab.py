"""The Patterns page tests: a pasted text, the 536 labelled complaints and a stress run.

Each function takes plain dicts (so it can run in a child process) and runs the normal readers
once with the saved patterns and once with the draft, by overriding the run-time settings.
"""

import re
from typing import Any

import app_settings
from app_settings.model import PatternEntry, PatternSettings, RuntimeSettings
from app_settings.patterns import joined
from complaint_processing.detectors import detect_signals
from complaint_rules.engine import Issue, RuleSpec, decide
from complaint_rules.matrix import read_default_matrix
from hallucination_checks.promises import sentence_checks
from pattern_lab.models import (
    CandidateOut,
    ClassificationOut,
    ClassifierCompare,
    Compare,
    DatasetCheckOut,
    DatasetHit,
    Hits,
    InjectionCompare,
    SentenceOut,
    SignalDelta,
    TextSide,
    TextTestOut,
)
from pattern_lab.sandbox import report
from python_validation.classifier import classify
from sample_complaints.evaluate import facts_for, load_dataset, prior_for, record_text

LISTED = 10  # changed complaints listed per section
_SENTENCE = "The parcel was late and the charger got very hot, we will refund you. "
STRESS_TEXTS = (
    "a" * 20_000 + "b",
    "a " * 10_000 + "b",
    "a!" * 10_000,
    (_SENTENCE * (20_000 // len(_SENTENCE) + 1))[:20_000],
)


def _sides(settings: dict[str, Any], draft: dict[str, Any]) -> dict[str, RuntimeSettings]:
    base = RuntimeSettings.model_validate(settings)
    new = PatternSettings.model_validate(draft)
    return {"saved": base, "draft": base.model_copy(update={"patterns": new})}


def try_text(
    settings: dict[str, Any], draft: dict[str, Any], text: str, taxonomy: dict[str, list[str]]
) -> dict[str, Any]:
    out: dict[str, TextSide] = {}
    for side, current in _sides(settings, draft).items():
        with app_settings.using(current):
            signals = detect_signals(text)
            result = classify(text, signals, taxonomy)
            sentences = sentence_checks(text)
        primary = result.primary
        out[side] = TextSide(
            signals=signals,
            classification=ClassificationOut(
                status=result.confidence,
                primary=f"{primary.category}/{primary.subcategory}" if primary else None,
                candidates=[
                    CandidateOut(category=c.category, subcategory=c.subcategory, score=c.score)
                    for c in result.candidates[:3]
                ],
            ),
            sentences=[SentenceOut(**vars(s)) for s in sentences],
        )
    return TextTestOut(**out).model_dump()


def _run_dataset(current: RuntimeSettings, taxonomy: dict[str, list[str]]) -> dict[str, Any]:
    data = load_dataset()
    rules = [RuleSpec.from_record(r) for r in read_default_matrix()]
    signals: dict[str, dict[str, list[str]]] = {}
    correct: set[str] = set()
    confident = escalation = urgency = 0
    with app_settings.using(current):
        for record in data.complaints:
            key, text, expected = record["dataset_id"], record_text(record), record["expected"]
            signals[key] = detect_signals(text)
            result = classify(text, signals[key], taxonomy)
            confident += result.confidence == "confident"
            if result.primary and (
                result.primary.category == expected["category"]
                or result.primary.category in expected.get("acceptable_categories", [])
            ):
                correct.add(key)
        accepted = data.accepted
        for record in accepted:
            expected = record["expected"]
            issues = [Issue(expected["category"], expected["subcategory"])] + [
                Issue(*s.split("/")) for s in expected["secondary_issues"]
            ]
            prior = prior_for(record, accepted)
            facts = facts_for(
                record, data.orders, data.customers, prior, signals[record["dataset_id"]]
            )
            decision = decide(rules, issues, facts)
            escalation += decision.escalation_level == expected["escalation_level"]
            urgency += decision.urgency == expected["urgency"]
    injected = {c["dataset_id"] for c in data.complaints if c["expected"]["prompt_injection"]}
    detected = {k for k, s in signals.items() if s.get("prompt_injection")}
    return {
        "signals": signals,
        "correct": correct,
        "confident": confident,
        "escalation": escalation,
        "urgency": urgency,
        "accepted": len(accepted),
        "injection": Hits(
            true_positive=len(detected & injected), false_positive=len(detected - injected)
        ),
    }


def dataset_check(
    settings: dict[str, Any], draft: dict[str, Any], taxonomy: dict[str, list[str]]
) -> dict[str, Any]:
    sides = _sides(settings, draft)
    saved, new = (_run_dataset(sides[s], taxonomy) for s in ("saved", "draft"))
    ids = list(saved["signals"])
    deltas = []
    for name in sides["draft"].patterns.signals:
        before = {k for k in ids if name in saved["signals"][k]}
        after = {k for k in ids if name in new["signals"][k]}
        deltas.append(
            SignalDelta(
                signal=name,
                saved=len(before),
                draft=len(after),
                gained=[
                    DatasetHit(dataset_id=k, phrases=new["signals"][k][name])
                    for k in ids
                    if k in after - before
                ][:LISTED],
                lost=[
                    DatasetHit(dataset_id=k, phrases=saved["signals"][k][name])
                    for k in ids
                    if k in before - after
                ][:LISTED],
            )
        )
    return DatasetCheckOut(
        total=len(ids),
        signals=deltas,
        classifier=ClassifierCompare(
            saved_correct=len(saved["correct"]),
            draft_correct=len(new["correct"]),
            saved_confident=saved["confident"],
            draft_confident=new["confident"],
            right_to_wrong=[k for k in ids if k in saved["correct"] - new["correct"]][:LISTED],
            wrong_to_right=[k for k in ids if k in new["correct"] - saved["correct"]][:LISTED],
        ),
        escalation=Compare(
            saved=saved["escalation"], draft=new["escalation"], total=saved["accepted"]
        ),
        urgency=Compare(saved=saved["urgency"], draft=new["urgency"], total=saved["accepted"]),
        prompt_injection=InjectionCompare(saved=saved["injection"], draft=new["injection"]),
    ).model_dump()


def _lists(patterns: PatternSettings) -> list[tuple[str, str]]:
    """(name, regex source) for every list, compiled the way the readers compile it."""

    def word(entries: list[PatternEntry]) -> str:
        return r"(?<!\w)(?:" + joined(entries) + r")(?!\w)"

    p = patterns.promises
    lists = [(name, word(entries)) for name, entries in patterns.signals.items()]
    lists += [
        (f"Classifier {category}/{sub}", word(list(entries)))
        for category, subs in patterns.classifier.items()
        for sub, entries in subs.items()
        if entries
    ]
    lists += [
        ("Promises commitment", joined(p.commitment, bounded=True)),
        ("Promises conditional", joined(p.conditional, bounded=True)),
        ("Deadline", p.deadline),
    ]
    lists += [(f"Promises kind {k}", joined(e, bounded=True)) for k, e in p.kinds.items()]
    return lists


def stress_check(draft: dict[str, Any]) -> None:
    """Run every list over long texts; run inside `run_limited` so a slow list is stopped."""
    for name, source in _lists(PatternSettings.model_validate(draft)):
        report(name)
        pattern = re.compile(source, re.IGNORECASE)
        for text in STRESS_TEXTS:
            for _ in pattern.finditer(text):
                pass
