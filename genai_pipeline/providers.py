"""GenAI provider adapters.

The pipeline talks to a small `LLMProvider` protocol, so the provider (Anthropic, Gemini,
OpenAI) is configuration. The provider and model of every call are logged.
"""

import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal, Protocol

import anthropic
from anthropic.types.beta import BetaMessageParam, BetaOutputConfigParam, BetaTextBlockParam

from src.core.config import get_settings

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class ProviderUnavailableError(Exception):
    """Transient failure (network, rate limit, overload) after the SDK's own retries."""


class ProviderRequestError(Exception):
    """Permanent failure (bad request, authentication): retrying will not help."""


@dataclass(frozen=True)
class LLMRequest:
    system: str
    user: str
    json_schema: dict[str, Any]
    max_tokens: int


@dataclass
class LLMResponse:
    text: str | None
    stop_reason: str | None
    model: str
    request_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    latency_ms: int = 0
    details: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    name: str
    model: str

    def complete(self, request: LLMRequest) -> LLMResponse: ...


class AnthropicProvider:
    """Claude via the Messages API with JSON-schema structured outputs.

    The system prompt (instructions + taxonomy) is identical across complaints, so it is
    marked for prompt caching. Server-side refusal fallbacks are enabled, so a request
    declined by the primary model's safety classifier is answered by another model instead
    of failing; `details` records which model actually answered.
    """

    name = "anthropic"
    FALLBACK_BETA = "server-side-fallback-2026-07-01"

    def __init__(self, model: str, effort: Effort, timeout_seconds: float, api_key: str | None):
        self.model = model
        self.effort = effort
        self._client = anthropic.Anthropic(
            api_key=api_key or None, timeout=timeout_seconds, max_retries=2
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        started = time.monotonic()
        system: list[BetaTextBlockParam] = [
            {"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}
        ]
        messages: list[BetaMessageParam] = [{"role": "user", "content": request.user}]
        output_config: BetaOutputConfigParam = {
            "effort": self.effort,
            "format": {"type": "json_schema", "schema": request.json_schema},
        }
        try:
            message = self._client.beta.messages.create(
                model=self.model,
                max_tokens=request.max_tokens,
                betas=[self.FALLBACK_BETA],
                fallbacks="default",
                system=system,
                messages=messages,
                output_config=output_config,
            )
        except (
            anthropic.RateLimitError,
            anthropic.InternalServerError,
            anthropic.APIConnectionError,
        ) as exc:
            raise ProviderUnavailableError(f"{type(exc).__name__}: {exc}") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                raise ProviderUnavailableError(f"HTTP {exc.status_code}: {exc.message}") from exc
            raise ProviderRequestError(f"HTTP {exc.status_code}: {exc.message}") from exc

        text = next((b.text for b in message.content if b.type == "text"), None)
        stop_details = message.stop_details  # set only when the model refused
        usage = message.usage
        return LLMResponse(
            text=text,
            stop_reason=message.stop_reason,
            model=message.model,
            request_id=getattr(message, "_request_id", None),
            input_tokens=usage.input_tokens or 0,
            output_tokens=usage.output_tokens or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            latency_ms=int((time.monotonic() - started) * 1000),
            details={
                "requested_model": self.model,
                "effort": self.effort,
                "stop_details": stop_details.to_dict() if stop_details else None,
            },
        )


@lru_cache
def get_provider() -> LLMProvider:
    settings = get_settings()
    if settings.genai_provider == "anthropic":
        return AnthropicProvider(
            model=settings.genai_model,
            effort=settings.genai_effort,
            timeout_seconds=settings.genai_timeout_seconds,
            api_key=settings.anthropic_api_key,
        )
    raise ProviderRequestError(f"Unsupported GenAI provider: {settings.genai_provider}")
