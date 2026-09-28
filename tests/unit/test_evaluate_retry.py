"""Long evaluation runs survive brief provider outages instead of stopping at the first one."""

from typing import Any

import pytest

from comparison_engine import evaluate
from genai_pipeline.providers import ProviderUnavailableError


def test_a_brief_outage_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    waits: list[float] = []

    def flaky(*_: Any, **__: Any) -> None:
        calls.append(1)
        if len(calls) < 3:
            raise ProviderUnavailableError("Connection error.")

    monkeypatch.setattr(evaluate, "run_analysis", flaky)
    evaluate.analyse_with_retries(None, "cid", None, None, None, wait=waits.append)
    assert len(calls) == 3
    assert waits == [30, 60]  # growing pauses between attempts


def test_a_lasting_outage_still_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    def down(*_: Any, **__: Any) -> None:
        raise ProviderUnavailableError("Connection error.")

    monkeypatch.setattr(evaluate, "run_analysis", down)
    with pytest.raises(ProviderUnavailableError):
        evaluate.analyse_with_retries(None, "cid", None, None, None, wait=lambda _: None)
