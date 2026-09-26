"""Test doubles for the GenAI provider. Used only in tests: the application itself always
calls a real provider (the SRS forbids fake GenAI responses in the product)."""

import copy
import json
from collections.abc import Callable
from typing import Any

from genai_pipeline.providers import LLMRequest, LLMResponse, ProviderUnavailableError

Script = str | Exception | Callable[[LLMRequest], str]


class ScriptedProvider:
    """Returns the scripted responses in order and records every request."""

    name = "scripted"
    model = "scripted-model"

    def __init__(self, *responses: Script, stop_reason: str = "end_turn"):
        self._responses = list(responses)
        self.stop_reason = stop_reason
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        text = item(request) if callable(item) else item
        return LLMResponse(
            text=text,
            stop_reason=self.stop_reason,
            model=self.model,
            request_id="req_test",
            input_tokens=1200,
            output_tokens=900,
            latency_ms=5,
        )


UNAVAILABLE = ProviderUnavailableError("RateLimitError: overloaded")

BASE_ANALYSIS: dict[str, Any] = {
    "complaint_summary": (
        "Standard order arrived 7 business days late; customer asks what compensation applies."
    ),
    "primary_issue": {
        "category": "DELIVERY",
        "subcategory": "DELAYED_DELIVERY",
        "description": "Order delivered late",
    },
    "secondary_issues": [],
    "sentiment": "Negative",
    "emotions": ["Frustration"],
    "urgency": "Medium",
    "urgency_rationale": "Delay without safety, privacy or legal risk.",
    "priority": "P2",
    "entities": {
        "products": ["AeroBook 14"],
        "order_refs": ["ORD-240001"],
        "transaction_refs": [],
        "complaint_refs": [],
        "dates": [],
        "amounts": [],
        "locations": [],
    },
    "department": "LOGISTICS",
    "supporting_departments": [],
    "policy_references": [],
    "resolution_steps": [
        {
            "action_code": "VERIFY_SHIPMENT_STATUS",
            "description": "Check courier tracking for ORD-240001.",
            "policy_chunk": None,
        },
        {
            "action_code": "CHECK_COMPENSATION_ELIGIBILITY",
            "description": "Confirm whether the delay qualifies for store credit.",
            "policy_chunk": None,
        },
    ],
    "compensation": {"offered": False, "type": "none", "amount": None, "policy_chunk": None},
    "escalation": {"required": False, "level": "NONE", "reason": None, "notes": None},
    "customer_response": {
        "tone": "Empathetic",
        "response_type": "Apology and Resolution Update",
        "subject": "Your delayed order",
        "body": "Thank you for contacting us about your delayed order. We are sorry it arrived "
        "late. We are checking the courier records and will confirm within 24 hours whether "
        "you are eligible for store credit. VoltHaven Electronics Customer Care",
    },
    "follow_up": {
        "required": True,
        "type": "DELIVERY_STATUS_UPDATE",
        "within_hours": 24,
        "message": "Update the customer on eligibility.",
    },
    "agent_guidance": ["Do not promise compensation before checking eligibility."],
    "missing_information": [],
    "clarification_questions": [],
    "suspicious_instructions": [],
}


def analysis_json(**overrides: Any) -> str:
    data = copy.deepcopy(BASE_ANALYSIS)
    data.update(overrides)
    return json.dumps(data)


def citing_first_policy(request: LLMRequest) -> str:
    """A valid answer that cites the first policy passage present in the prompt."""
    marker = 'chunk_code="'
    start = request.user.index(marker) + len(marker)
    chunk_code = request.user[start : request.user.index('"', start)]
    doc_code = chunk_code.split("@")[0]
    return analysis_json(
        policy_references=[
            {
                "chunk_code": chunk_code,
                "doc_code": doc_code,
                "section": None,
                "applicability": "applicable",
                "reason": "Defines delivery commitments.",
            }
        ]
    )
