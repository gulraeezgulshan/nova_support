"""Knowledge-base and AI values in the run-time settings: defaults, limits, per-group fallback."""

from typing import Any

import pytest
from pydantic import ValidationError

import app_settings
from app_settings import load
from app_settings.model import KnowledgeBaseSettings


def kb(**changes: Any) -> dict[str, Any]:
    return {**app_settings.defaults().knowledge_base.model_dump(), **changes}


def test_defaults_equal_today() -> None:
    d = app_settings.defaults()
    k = d.knowledge_base
    assert (k.chunk_max_tokens, k.chunk_overlap_tokens, k.max_upload_mb,
            k.retrieval_candidates, k.rrf_k) == (450, 60, 20, 30, 60)  # fmt: skip
    assert [(t.code, t.precedence) for t in k.document_types][:2] == [
        ("compliance", 1),
        ("policy", 2),
    ]
    assert len(k.document_types) == 9
    assert (d.ai.timeout_seconds, d.ai.max_attempts, d.ai.openai_reasoning) == (60.0, 2, True)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("chunk_max_tokens", 99),
        ("chunk_max_tokens", 481),
        ("max_upload_mb", 0),
        ("max_upload_mb", 51),
        ("retrieval_candidates", 4),
        ("retrieval_candidates", 101),
        ("rrf_k", 0),
        ("rrf_k", 201),
    ],
)
def test_kb_limits(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        KnowledgeBaseSettings.model_validate(kb(**{field: value}))


def test_overlap_must_leave_50_tokens() -> None:
    with pytest.raises(ValidationError):
        KnowledgeBaseSettings.model_validate(kb(chunk_max_tokens=200, chunk_overlap_tokens=151))
    ok = KnowledgeBaseSettings.model_validate(kb(chunk_max_tokens=200, chunk_overlap_tokens=150))
    assert ok.chunk_overlap_tokens == 150


@pytest.mark.parametrize(
    "types",
    [
        [{"code": "policy", "name": "Policy", "precedence": 2}] * 2,
        [{"code": "Policy", "name": "Policy", "precedence": 2}],
        [{"code": "policy", "name": "ab", "precedence": 2}],
        [{"code": "policy", "name": "Policy", "precedence": 0}],
        [{"code": "policy", "name": "Policy", "precedence": 10}],
        [],
    ],
)
def test_document_type_rules(types: list[dict[str, Any]]) -> None:
    with pytest.raises(ValidationError):
        KnowledgeBaseSettings.model_validate(kb(document_types=types))


@pytest.mark.parametrize(
    ("field", "value"),
    [("timeout_seconds", 9), ("timeout_seconds", 301), ("max_attempts", 0), ("max_attempts", 4)],
)
def test_ai_limits(field: str, value: float) -> None:
    ai = {**app_settings.defaults().ai.model_dump(), field: value}
    with pytest.raises(ValidationError):
        type(app_settings.defaults().ai).model_validate(ai)


def test_bad_kb_group_resets_only_that_group() -> None:
    s = load({"knowledge_base": {"chunk_max_tokens": 5}, "email": {"mailbox_check_seconds": 120}})
    assert s.knowledge_base.chunk_max_tokens == 450
    assert s.email.mailbox_check_seconds == 120


def test_valid_kb_change_is_kept() -> None:
    s = load({"knowledge_base": {"chunk_max_tokens": 300, "chunk_overlap_tokens": 40}})
    assert (s.knowledge_base.chunk_max_tokens, s.knowledge_base.chunk_overlap_tokens) == (300, 40)
