"""One turn of the guided intake: ask the next question or propose a summary.

The GenAI only gathers information. Its reply is checked for commitments (refunds, dates,
...) and replaced with a neutral question if it makes one; invalid output is retried once,
and any failure falls back to fixed questions, so the chat always works.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import ValidationError

from genai_pipeline.output_schema import strict_schema
from genai_pipeline.prompts import load_template
from genai_pipeline.providers import (
    LLMProvider,
    LLMRequest,
    ProviderRequestError,
    ProviderUnavailableError,
)
from hallucination_checks.promises import find_promises
from python_validation.types import validation_config
from schemas.chat_intake import IntakeTurn
from src.core.logging import get_logger

log = get_logger(__name__)

MAX_QUESTIONS = 6
FALLBACK_QUESTIONS = [
    "What happened? Please describe the problem.",
    "When did this happen?",
    "What would you like us to do about it?",
]
NEUTRAL_QUESTION = "Thanks. Is there anything else about the problem we should know?"
ATTEMPTS = 2


def deadline_pattern() -> re.Pattern[str]:
    """Any timeline ("within 24 hours", "by Friday") — the chat never commits to one."""
    return re.compile(validation_config()["promises"]["deadline"], re.IGNORECASE)


@dataclass
class IntakeResult:
    reply: str
    title: str
    requested_resolution: str | None
    ready: bool
    source: Literal["genai", "fallback"]
    details: dict[str, Any] = field(default_factory=dict)


MIN_TITLE_CHARS = 5  # the intake's minimum (complaint_processing.service)


def _fallback_title(customer_messages: list[str], order: dict[str, str] | None) -> str:
    """A title that always passes intake: the customer's words, or the product as context."""
    words = " ".join(" ".join(customer_messages).split())[:80]
    title = (
        words if len(words) >= 20 or not order else f"Problem with {order['product_name']}: {words}"
    )
    return title[:80] if len(title) >= MIN_TITLE_CHARS else f"Customer complaint: {title}"[:80]


def _safe_title(title: str, customer_messages: list[str], order: dict[str, str] | None) -> str:
    title = title.strip()[:80]
    return title if len(title) >= MIN_TITLE_CHARS else _fallback_title(customer_messages, order)


def fallback_turn(
    customer_messages: list[str], reason: str, order: dict[str, str] | None = None
) -> IntakeResult:
    answered = len(customer_messages)  # the first message answers "what happened"
    ready = answered >= len(FALLBACK_QUESTIONS)
    reply = "Thanks, here is what I'll send to our team:" if ready else FALLBACK_QUESTIONS[answered]
    # The third message answers "What would you like us to do?"; later ones are corrections.
    wanted = customer_messages[len(FALLBACK_QUESTIONS) - 1] if ready else None
    return IntakeResult(
        reply,
        _fallback_title(customer_messages, order),
        wanted,
        ready,
        "fallback",
        {"reason": reason},
    )


def next_turn(
    provider: LLMProvider | None, *, order: dict[str, str] | None, customer_messages: list[str]
) -> IntakeResult:
    if provider is None:
        return fallback_turn(customer_messages, "no GenAI provider configured", order)
    template = load_template("chat_intake")
    questions_asked = max(0, len(customer_messages) - 1)
    must_summarise = questions_asked >= MAX_QUESTIONS
    system, user = template.render(
        order=order,
        messages=customer_messages,
        questions_asked=questions_asked,
        max_questions=MAX_QUESTIONS,
        must_summarise=must_summarise,
    )
    request = LLMRequest(
        system=system,
        user=user,
        json_schema=strict_schema(IntakeTurn),
        max_tokens=int(template.parameters.get("max_tokens", 1500)),
    )
    errors: list[str] = []
    for _ in range(ATTEMPTS):
        try:
            response = provider.complete(request)
        except (ProviderUnavailableError, ProviderRequestError) as exc:
            log.warning("chat_intake.provider_failed", error=str(exc))
            return fallback_turn(customer_messages, f"provider: {exc}", order)
        except Exception as exc:  # any other SDK failure: the chat must keep working
            log.exception("chat_intake.provider_error")
            return fallback_turn(customer_messages, f"provider error: {type(exc).__name__}", order)
        try:
            parsed = IntakeTurn.model_validate(json.loads(response.text or ""))
        except (json.JSONDecodeError, ValidationError) as exc:
            errors.append(str(exc)[:300])
            continue
        details = {
            "provider": provider.name,
            "model": response.model,
            "prompt": f"{template.name}@{template.version}",
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "latency_ms": response.latency_ms,
            "promise_removed": False,
        }
        reply = parsed.reply.strip()
        if find_promises(reply) or deadline_pattern().search(reply):
            reply, details["promise_removed"] = NEUTRAL_QUESTION, True
        return IntakeResult(
            reply,
            _safe_title(parsed.title, customer_messages, order),
            parsed.requested_resolution,
            parsed.ready_to_confirm or must_summarise,
            "genai",
            details,
        )
    return fallback_turn(customer_messages, "invalid output: " + " | ".join(errors), order)
