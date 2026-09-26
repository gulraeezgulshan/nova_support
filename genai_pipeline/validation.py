"""Python validation of the GenAI JSON output (SRS Step 46).

Checks required fields and types (Pydantic), then every code against the live vocabulary:
valid category/subcategory pairs, urgency, priority, department IDs, action codes,
escalation status, and that every policy reference is a passage that was actually
retrieved for this complaint. Errors are returned as plain sentences so they can be fed
back to the model on a retry and shown to reviewers.

Deeper business-rule checks (the Ground-Truth Validation Pipeline) run separately.
"""

import json
from collections.abc import Mapping

from pydantic import ValidationError

from genai_pipeline.vocabulary import Vocabulary
from schemas.complaint_analysis import ComplaintAnalysis, Issue

MIN_RESPONSE_CHARS = 80


def parse_and_validate(
    text: str | None, vocab: Vocabulary, retrieved: Mapping[str, str]
) -> tuple[ComplaintAnalysis | None, list[str]]:
    """`retrieved` maps each chunk_code given to the model to its document ID."""
    if not text or not text.strip():
        return None, ["The response was empty."]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [f"The response is not valid JSON ({exc.msg} at position {exc.pos})."]
    try:
        analysis = ComplaintAnalysis.model_validate(data)
    except ValidationError as exc:
        return None, [
            f"Field '{'.'.join(str(p) for p in err['loc'])}': {err['msg']}." for err in exc.errors()
        ]
    return analysis, check_vocabulary(analysis, vocab, retrieved)


def _issue_errors(issue: Issue, label: str, vocab: Vocabulary) -> list[str]:
    if issue.category not in vocab.categories:
        return [f"{label} category '{issue.category}' is not a valid category."]
    if issue.subcategory not in vocab.categories[issue.category]:
        return [
            f"{label} subcategory '{issue.subcategory}' does not belong to category "
            f"'{issue.category}' (valid: {', '.join(vocab.categories[issue.category])})."
        ]
    return []


def check_vocabulary(
    a: ComplaintAnalysis, vocab: Vocabulary, retrieved: Mapping[str, str]
) -> list[str]:
    errors = _issue_errors(a.primary_issue, "Primary issue", vocab)
    for index, issue in enumerate(a.secondary_issues, start=1):
        errors += _issue_errors(issue, f"Secondary issue {index}", vocab)
        if (issue.category, issue.subcategory) == (
            a.primary_issue.category,
            a.primary_issue.subcategory,
        ):
            errors.append(f"Secondary issue {index} repeats the primary issue.")

    def check(value: str | None, allowed: object, label: str) -> None:
        if value is not None and value not in allowed:  # type: ignore[operator]
            errors.append(f"{label} '{value}' is not an allowed value.")

    check(a.sentiment, vocab.sentiments, "Sentiment")
    check(a.urgency, vocab.urgencies, "Urgency")
    check(a.priority, vocab.priorities, "Priority")
    check(a.department, vocab.departments, "Department")
    for emotion in a.emotions:
        check(emotion, vocab.emotions, "Emotion")
    for dept in a.supporting_departments:
        check(dept, vocab.departments, "Supporting department")
    if a.department in a.supporting_departments:
        errors.append("The primary department must not also be a supporting department.")

    for step in a.resolution_steps:
        check(step.action_code, vocab.actions, "Action code")
        if step.policy_chunk and step.policy_chunk not in retrieved:
            errors.append(
                f"Resolution step cites '{step.policy_chunk}', which was not among the "
                "provided policy passages."
            )
    if not a.resolution_steps:
        errors.append("At least one resolution step is required.")

    for ref in a.policy_references:
        check(ref.applicability, vocab.policy_applicability, "Policy applicability")
        if ref.chunk_code not in retrieved:
            errors.append(
                f"Policy reference '{ref.chunk_code}' was not among the provided policy passages."
            )
        elif retrieved[ref.chunk_code] != ref.doc_code:
            errors.append(
                f"Policy reference '{ref.chunk_code}' belongs to {retrieved[ref.chunk_code]}, "
                f"not {ref.doc_code}."
            )

    check(a.escalation.level, vocab.escalation_levels, "Escalation level")
    if a.escalation.required and a.escalation.level == "NONE":
        errors.append("Escalation is required but the level is NONE.")
    if not a.escalation.required and a.escalation.level != "NONE":
        errors.append("Escalation level is set but escalation.required is false.")
    if a.escalation.required and a.escalation.notes is None:
        errors.append("Escalation notes are required when escalating.")

    check(a.compensation.type, vocab.compensation_types, "Compensation type")
    if a.compensation.offered and a.compensation.type == "none":
        errors.append("Compensation is offered but its type is 'none'.")
    if a.compensation.policy_chunk and a.compensation.policy_chunk not in retrieved:
        errors.append("Compensation cites a policy passage that was not provided.")

    check(a.customer_response.tone, vocab.response_tones, "Response tone")
    check(a.customer_response.response_type, vocab.response_types, "Response type")
    if len(a.customer_response.body.strip()) < MIN_RESPONSE_CHARS:
        errors.append("The customer response body is too short.")

    check(a.follow_up.type, vocab.follow_up_types, "Follow-up type")
    if a.follow_up.required and (a.follow_up.type is None or a.follow_up.within_hours is None):
        errors.append("A required follow-up needs a type and within_hours.")
    if a.follow_up.within_hours is not None and a.follow_up.within_hours <= 0:
        errors.append("follow_up.within_hours must be positive.")
    return errors
