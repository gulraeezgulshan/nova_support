"""GenAI provider adapters.

The pipeline talks to a small `LLMProvider` protocol, so the provider is configuration
(`GENAI_PROVIDER=anthropic` or `openai`). Both adapters send the same prompt and the same
JSON schema and return the same `LLMResponse`, so Pipeline 1's validation and Pipeline 2 do
not change. The provider and model of every call are logged.
"""

import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal, Protocol

import anthropic
import openai
from anthropic.types.beta import BetaMessageParam, BetaOutputConfigParam, BetaTextBlockParam

import app_settings
from src.core.config import get_settings

Effort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]
ClaudeEffort = Literal["low", "medium", "high", "xhigh", "max"]


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
        # Claude's lowest effort is "low"; "none" and "minimal" exist only on OpenAI.
        self.effort: ClaudeEffort = "low" if effort == "none" or effort == "minimal" else effort
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


def openai_strict_schema(node: Any) -> Any:
    """OpenAI's strict mode rejects keywords next to `$ref`; keep the reference alone."""
    if isinstance(node, dict):
        if "$ref" in node:
            return {"$ref": node["$ref"]}
        return {key: openai_strict_schema(value) for key, value in node.items()}
    if isinstance(node, list):
        return [openai_strict_schema(item) for item in node]
    return node


class OpenAIProvider:
    """OpenAI via the Responses API with strict JSON-schema structured outputs.

    Mapped onto the same response shape as Claude: a refusal becomes `stop_reason="refusal"`
    and a response cut off by the token limit becomes `"max_tokens"`, so the pipeline's
    retry and manual-review handling is identical for both providers.
    """

    name = "openai"
    SCHEMA_NAME = "complaint_analysis"

    def __init__(
        self,
        model: str,
        effort: Effort,
        timeout_seconds: float,
        api_key: str | None,
        reasoning: bool = True,
    ):
        self.model = model
        self.effort = effort
        self.reasoning = reasoning
        self._client = openai.OpenAI(
            api_key=api_key or None, timeout=timeout_seconds, max_retries=2
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        started = time.monotonic()
        options: dict[str, Any] = {}
        if self.reasoning:  # reasoning models only; set OPENAI_REASONING=false otherwise
            options["reasoning"] = {"effort": self.effort}
        try:
            response = self._client.responses.create(
                model=self.model,
                instructions=request.system,
                input=request.user,
                max_output_tokens=request.max_tokens,
                store=False,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": self.SCHEMA_NAME,
                        "schema": openai_strict_schema(request.json_schema),
                        "strict": True,
                    }
                },
                **options,
            )
        except (
            openai.RateLimitError,
            openai.InternalServerError,
            openai.APIConnectionError,
        ) as exc:
            raise ProviderUnavailableError(f"{type(exc).__name__}: {exc}") from exc
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                raise ProviderUnavailableError(f"HTTP {exc.status_code}: {exc.message}") from exc
            raise ProviderRequestError(f"HTTP {exc.status_code}: {exc.message}") from exc

        text: str | None = None
        refusal: str | None = None
        for item in response.output:
            if item.type != "message":
                continue
            for part in item.content:
                if part.type == "output_text":
                    text = (text or "") + part.text
                elif part.type == "refusal":
                    refusal = part.refusal
        incomplete = response.incomplete_details.reason if response.incomplete_details else None
        if refusal is not None or incomplete == "content_filter":
            stop_reason = "refusal"
        elif incomplete == "max_output_tokens":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"
        usage = response.usage
        cached = usage.input_tokens_details.cached_tokens if usage else 0
        return LLMResponse(
            text=None if stop_reason == "refusal" else text,
            stop_reason=stop_reason,
            model=response.model,
            request_id=getattr(response, "_request_id", None) or response.id,
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
            cache_read_tokens=cached or 0,
            latency_ms=int((time.monotonic() - started) * 1000),
            details={
                "requested_model": self.model,
                "effort": self.effort if self.reasoning else None,
                "status": response.status,
                "incomplete_reason": incomplete,
                "refusal": refusal,
            },
        )


def get_provider() -> LLMProvider:
    """The provider and model chosen on the Settings page; keys stay in the environment."""
    ai = app_settings.runtime().ai
    return _build_provider(ai.provider, ai.model, ai.effort)


@lru_cache(maxsize=4)
def _build_provider(provider: str, model: str, effort: Effort) -> LLMProvider:
    settings = get_settings()
    if provider == "anthropic":
        return AnthropicProvider(
            model=model, effort=effort, timeout_seconds=settings.genai_timeout_seconds,
            api_key=settings.anthropic_api_key,
        )  # fmt: skip
    if provider == "openai":
        return OpenAIProvider(
            model=model, effort=effort, timeout_seconds=settings.genai_timeout_seconds,
            api_key=settings.openai_api_key, reasoning=settings.openai_reasoning,
        )  # fmt: skip
    raise ProviderRequestError(f"Unsupported GenAI provider: {provider}")
