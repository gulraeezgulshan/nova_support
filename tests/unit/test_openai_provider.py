"""The OpenAI adapter, against a mocked HTTP transport (no key, no network).

It must send the same prompt and strict JSON schema as the Claude adapter and map OpenAI's
refusals, truncation and errors onto the pipeline's common response and error types.
"""

import json
from collections.abc import Callable
from typing import Any

import httpx2
import openai
import pytest

from genai_pipeline.providers import (
    LLMRequest,
    OpenAIProvider,
    ProviderRequestError,
    ProviderUnavailableError,
    get_provider,
    openai_strict_schema,
)
from src.core.config import Settings
from tests.fixtures.settings import use_settings

SCHEMA = {
    "type": "object",
    "properties": {"issue": {"$ref": "#/$defs/Issue", "description": "Primary issue"}},
    "required": ["issue"],
    "additionalProperties": False,
    "$defs": {
        "Issue": {
            "type": "object",
            "properties": {"category": {"type": "string", "enum": ["DELIVERY"]}},
            "required": ["category"],
            "additionalProperties": False,
        }
    },
}
REQUEST = LLMRequest(
    system="You analyse complaints.",
    user="<complaint>late</complaint>",
    json_schema=SCHEMA,
    max_tokens=4000,
)


def response_body(content: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {
        "id": "resp_123",
        "object": "response",
        "created_at": 1790000000,
        "model": "gpt-5-mini-2026-08-01",
        "status": "completed",
        "incomplete_details": None,
        "error": None,
        "output": [
            {
                "type": "message",
                "id": "msg_1",
                "role": "assistant",
                "status": "completed",
                "content": content,
            }
        ],
        "usage": {
            "input_tokens": 1200,
            "input_tokens_details": {"cached_tokens": 800},
            "output_tokens": 300,
            "output_tokens_details": {"reasoning_tokens": 100},
            "total_tokens": 1500,
        },
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        **extra,
    }


def provider_with(
    handler: Callable[[httpx2.Request], httpx2.Response], reasoning: bool = True
) -> tuple[OpenAIProvider, list[dict[str, Any]]]:
    sent: list[dict[str, Any]] = []

    def record(request: httpx2.Request) -> httpx2.Response:
        sent.append(json.loads(request.content))
        return handler(request)

    provider = OpenAIProvider("gpt-5-mini", "low", 30, "sk-test", reasoning=reasoning)
    provider._client = openai.OpenAI(
        api_key="sk-test",
        max_retries=0,
        http_client=openai.DefaultHttpxClient(transport=httpx2.MockTransport(record)),
    )
    return provider, sent


def test_valid_answer_and_request_shape() -> None:
    answer = '{"issue": {"category": "DELIVERY"}}'
    provider, sent = provider_with(
        lambda _: httpx2.Response(
            200, json=response_body([{"type": "output_text", "text": answer, "annotations": []}])
        )
    )
    result = provider.complete(REQUEST)

    assert (result.text, result.stop_reason) == (answer, "end_turn")
    assert result.model == "gpt-5-mini-2026-08-01"
    assert (result.input_tokens, result.output_tokens, result.cache_read_tokens) == (1200, 300, 800)
    body = sent[0]
    assert body["model"] == "gpt-5-mini" and body["instructions"] == REQUEST.system
    assert body["input"] == REQUEST.user and body["max_output_tokens"] == 4000
    assert body["store"] is False and body["reasoning"] == {"effort": "low"}
    fmt = body["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True
    assert fmt["schema"]["properties"]["issue"] == {"$ref": "#/$defs/Issue"}


def test_reasoning_can_be_turned_off() -> None:
    provider, sent = provider_with(
        lambda _: httpx2.Response(
            200, json=response_body([{"type": "output_text", "text": "{}", "annotations": []}])
        ),
        reasoning=False,
    )
    provider.complete(REQUEST)
    assert "reasoning" not in sent[0]


def test_refusal_is_reported_as_refusal() -> None:
    provider, _ = provider_with(
        lambda _: httpx2.Response(
            200, json=response_body([{"type": "refusal", "refusal": "I can't help with that."}])
        )
    )
    result = provider.complete(REQUEST)
    assert (result.text, result.stop_reason) == (None, "refusal")
    assert result.details["refusal"] == "I can't help with that."


def test_truncated_answer_is_reported_as_max_tokens() -> None:
    provider, _ = provider_with(
        lambda _: httpx2.Response(
            200,
            json=response_body(
                [{"type": "output_text", "text": '{"issue": {', "annotations": []}],
                status="incomplete",
                incomplete_details={"reason": "max_output_tokens"},
            ),
        )
    )
    assert provider.complete(REQUEST).stop_reason == "max_tokens"


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (429, ProviderUnavailableError),
        (503, ProviderUnavailableError),
        (401, ProviderRequestError),
        (400, ProviderRequestError),
    ],
)
def test_errors_map_to_transient_or_permanent(status: int, error: type[Exception]) -> None:
    provider, _ = provider_with(
        lambda _: httpx2.Response(status, json={"error": {"message": "nope", "type": "x"}})
    )
    with pytest.raises(error):
        provider.complete(REQUEST)


def test_strict_schema_keeps_refs_alone() -> None:
    cleaned = openai_strict_schema(SCHEMA)
    assert cleaned["properties"]["issue"] == {"$ref": "#/$defs/Issue"}
    assert cleaned["$defs"] == SCHEMA["$defs"]


def test_provider_is_chosen_by_one_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(genai_provider="openai", openai_api_key="sk-test", openai_model="gpt-x")
    assert (settings.genai_model, settings.genai_api_key_name) == ("gpt-x", "OPENAI_API_KEY")
    monkeypatch.setattr("genai_pipeline.providers.get_settings", lambda: settings)
    use_settings(ai={"provider": "openai", "model": "gpt-x"})
    provider = get_provider()
    assert (provider.name, provider.model) == ("openai", "gpt-x")
    claude = Settings(genai_provider="anthropic", anthropic_model="claude-opus-5")
    assert (claude.genai_model, claude.genai_api_key_name) == ("claude-opus-5", "ANTHROPIC_API_KEY")


def test_old_genai_model_setting_still_sets_the_claude_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GENAI_MODEL", "claude-sonnet-5")
    assert Settings(_env_file=None).anthropic_model == "claude-sonnet-5"


@pytest.mark.parametrize("effort", ["none", "minimal"])
def test_openai_only_effort_levels_fall_back_to_low_on_claude(effort: str) -> None:
    from genai_pipeline.providers import AnthropicProvider

    assert AnthropicProvider("claude-opus-5", effort, 30, "sk-ant-test").effort == "low"  # type: ignore[arg-type]
