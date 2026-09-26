"""Build the JSON schema sent to the model as a structured-output constraint.

Starts from the Pydantic contract, removes keywords the structured-output feature does not
support, forces `additionalProperties: false` and all-required objects, and injects `enum`
lists for every code field from the live vocabulary.
"""

import hashlib
import json
from typing import Any

from genai_pipeline.vocabulary import Vocabulary
from schemas.complaint_analysis import ComplaintAnalysis

_DROP_KEYS = {"title", "default"}


def _clean(node: Any) -> Any:
    if isinstance(node, dict):
        cleaned = {k: _clean(v) for k, v in node.items() if k not in _DROP_KEYS}
        if cleaned.get("type") == "object" and "properties" in cleaned:
            cleaned["additionalProperties"] = False
            cleaned["required"] = list(cleaned["properties"])
        return cleaned
    if isinstance(node, list):
        return [_clean(v) for v in node]
    return node


def _set_enum(node: dict[str, Any], values: list[str]) -> None:
    """Constrain a string field (plain, nullable via anyOf, or an array of strings)."""
    if "anyOf" in node:
        for branch in node["anyOf"]:
            if branch.get("type") != "null":
                _set_enum(branch, values)
    elif node.get("type") == "array":
        _set_enum(node["items"], values)
    else:
        node["enum"] = list(values)


def build_json_schema(vocab: Vocabulary) -> dict[str, Any]:
    schema: dict[str, Any] = _clean(ComplaintAnalysis.model_json_schema())
    defs = schema["$defs"]
    targets: list[tuple[dict[str, Any], str, list[str]]] = [
        (defs["Issue"], "category", list(vocab.categories)),
        (defs["Issue"], "subcategory", vocab.all_subcategories),
        (schema, "sentiment", vocab.sentiments),
        (schema, "emotions", vocab.emotions),
        (schema, "urgency", vocab.urgencies),
        (schema, "priority", list(vocab.priorities)),
        (schema, "department", list(vocab.departments)),
        (schema, "supporting_departments", list(vocab.departments)),
        (defs["PolicyReference"], "applicability", vocab.policy_applicability),
        (defs["ResolutionStep"], "action_code", list(vocab.actions)),
        (defs["Escalation"], "level", list(vocab.escalation_levels)),
        (defs["Compensation"], "type", vocab.compensation_types),
        (defs["CustomerResponse"], "tone", vocab.response_tones),
        (defs["CustomerResponse"], "response_type", vocab.response_types),
        (defs["FollowUp"], "type", vocab.follow_up_types),
    ]
    for owner, field, values in targets:
        _set_enum(owner["properties"][field], values)
    return schema


def schema_version(schema: dict[str, Any]) -> str:
    """Short, stable fingerprint of the exact schema used for an analysis."""
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]
