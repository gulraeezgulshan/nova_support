"""The knowledge-base and AI settings reach the code that uses them."""

import itertools
import re
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy import select

import app_settings
from database.models import AppSettingsRow, Chunk, Role, RunStatus
from database.session import sync_session
from knowledge_base import retrieval
from knowledge_base.config import get_kb_config
from knowledge_base.embeddings import get_embedder
from tests.fixtures.genai import ScriptedProvider, analysis_json, citing_first_policy
from tests.integration.test_analysis_pipeline import analyse
from tests.integration.test_documents_api import run_ingest

pytestmark = pytest.mark.db

PARA = (
    "When a repair request arrives, the agent first confirms the order, the product model and "
    "the serial number, and checks that the device is still inside its warranty period. The "
    "agent then asks the customer to describe the fault in their own words, when it started, and "
    "whether it happens every time or only sometimes. If the customer reports heat, smoke, "
    "sparks, swelling or a burning smell, the agent stops the repair process immediately, tells "
    "the customer to stop using the device and follows the product safety procedure instead. "
)
LONG_SOP = (
    "# Repair Handling Procedure\n\nDocument ID: TST-SOP-01\nDocument Type: sop\nVersion: 1.0\n"
    "Effective Date: 2026-10-01\n\n## 1 Purpose\n\nHow agents handle repair requests.\n\n"
    "## 2 First Contact\n\n" + "\n\n".join([PARA] * 6) + "\n"
)


def settings_with(**groups: dict[str, Any]) -> app_settings.RuntimeSettings:
    return app_settings.load(groups)


async def upload_md(client: httpx.AsyncClient, headers: dict[str, str], data: bytes) -> Any:
    return await client.post(
        "/api/v1/documents/upload",
        files={"file": ("procedure.md", data, "text/markdown")},
        data={"activate": "true"},
        headers=headers,
    )


async def test_ingestion_uses_chunk_size_saved_after_cache_filled(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    r = await upload_md(client, auth_headers(Role.ADMIN), LONG_SOP.encode())
    assert r.status_code == 202, r.text
    app_settings.runtime()  # fill the cache with the defaults (450 / 60)
    with sync_session() as db:  # another process saves 200 / 0 without resetting our cache
        db.merge(
            AppSettingsRow(
                id=1,
                data={"knowledge_base": {"chunk_max_tokens": 200, "chunk_overlap_tokens": 0}},
                version=1,
            )
        )
    run_ingest(r.json()["id"])
    with sync_session() as db:
        chunks = list(db.scalars(select(Chunk).order_by(Chunk.ordinal)))
    assert chunks and all(c.token_count <= 200 for c in chunks)
    assert len(chunks) > 5  # with 450 tokens this document gives 5 passages
    for before, after in itertools.pairwise(chunks):
        last = re.split(r"(?<=[.!?])\s+", before.content.strip())[-1]
        assert not after.content.startswith(last)  # overlap 0: nothing repeated


async def test_upload_limit_from_settings(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    app_settings.override(settings_with(knowledge_base={"max_upload_mb": 1}))
    big = LONG_SOP.encode() + b"x" * (2 * 1024 * 1024)
    r = await upload_md(client, auth_headers(Role.ADMIN), big)
    assert r.status_code == 422
    assert "the limit is 1 MB" in r.text


async def test_retrieval_reads_candidates_and_k(
    clean_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[int, int]] = []
    real_fuse = retrieval._fuse

    def recording_fuse(rankings: Any, limit: int, k: int) -> Any:
        seen.append((k, max((len(r) for r in rankings), default=0)))
        return real_fuse(rankings, limit, k)

    monkeypatch.setattr(retrieval, "_fuse", recording_fuse)
    from database.session import async_session_factory

    app_settings.override(settings_with(knowledge_base={"rrf_k": 10, "retrieval_candidates": 5}))
    async with async_session_factory()() as db:
        await retrieval.search_chunks(db, "late delivery", get_embedder(), 3)
    app_settings.override(app_settings.defaults())
    async with async_session_factory()() as db:
        await retrieval.search_chunks(db, "late delivery", get_embedder(), 3)
    assert [k for k, _ in seen] == [10, 60]


def test_document_types_from_settings() -> None:
    types = [t.model_dump() for t in app_settings.defaults().knowledge_base.document_types]
    for t in types:
        if t["code"] == "faq":
            t["precedence"] = 1
    types.append({"code": "notice", "name": "Notice", "precedence": 3})
    app_settings.override(settings_with(knowledge_base={"document_types": types}))
    config = get_kb_config()
    assert "notice" in config.type_codes
    assert {t.code: t.precedence for t in config.document_types}["faq"] == 1


def test_provider_rebuilt_when_timeout_or_reasoning_changes() -> None:
    from genai_pipeline.providers import get_provider

    ai = app_settings.defaults().ai.model_dump()
    app_settings.override(settings_with(ai={**ai, "provider": "openai", "timeout_seconds": 30}))
    first = get_provider()
    assert first.timeout_seconds == 30
    app_settings.override(
        settings_with(
            ai={**ai, "provider": "openai", "timeout_seconds": 90, "openai_reasoning": False}
        )
    )
    second = get_provider()
    assert second.timeout_seconds == 90 and second.reasoning is False


def test_attempts_from_settings(complaint_id: uuid.UUID) -> None:
    ai = app_settings.defaults().ai.model_dump()
    app_settings.override(settings_with(ai={**ai, "max_attempts": 1}))
    provider = ScriptedProvider(analysis_json(department="MARKETING"), citing_first_policy)
    run = analyse(complaint_id, provider)
    assert (run.status, run.attempts, len(provider.requests)) == (RunStatus.NEEDS_REVIEW, 1, 1)
