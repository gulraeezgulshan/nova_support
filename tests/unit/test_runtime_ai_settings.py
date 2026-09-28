"""AI settings from the Settings page reach the provider, retrieval and verdicts."""

import pytest

from genai_pipeline.providers import get_provider
from src.core.config import Settings
from tests.fixtures.settings import use_settings


def test_provider_and_model_come_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "genai_pipeline.providers.get_settings",
        lambda: Settings(openai_api_key="sk-test", anthropic_api_key="ak-test"),
    )
    use_settings(ai={"provider": "openai", "model": "gpt-5", "effort": "minimal"})
    provider = get_provider()
    assert (provider.name, provider.model) == ("openai", "gpt-5")
    use_settings(ai={"provider": "anthropic", "model": "claude-sonnet-5", "effort": "low"})
    assert (get_provider().name, get_provider().model) == ("anthropic", "claude-sonnet-5")


def test_review_thresholds_come_from_settings() -> None:
    from python_validation.checks import verdict_config

    use_settings(operations={"verified_min_score": 95, "always_review_escalation_level": 2})
    cfg = verdict_config()
    assert (cfg["verified_min_score"], cfg["always_review_escalation_level"]) == (95, 2)
