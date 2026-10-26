"""Reprocess all active documents: re-queues every active version, keeps it active, audits."""

import uuid
from collections.abc import Callable

import httpx
import pytest
from sqlalchemy import select

import app_settings
from database.models import AuditEvent, DocumentVersion, Role
from database.session import sync_session
from tests.integration.test_documents_api import run_ingest

pytestmark = pytest.mark.db
URL = "/api/v1/documents/reprocess-active"


def policy(doc_id: str, version: str) -> bytes:
    return (
        f"# {doc_id} Policy\n\nDocument ID: {doc_id}\nDocument Type: policy\nVersion: {version}\n"
        "Effective Date: 2026-01-01\n\n## 1 Purpose\n\nA short test policy about refunds.\n"
    ).encode()


async def add(client: httpx.AsyncClient, admin: dict[str, str], doc_id: str, version: str) -> str:
    r = await client.post(
        "/api/v1/documents/upload",
        files={"file": (f"{doc_id}-{version}.md", policy(doc_id, version), "text/markdown")},
        data={"activate": "true"},
        headers=admin,
    )
    assert r.status_code == 202, r.text
    run_ingest(r.json()["id"])
    version_id: str = r.json()["id"]
    return version_id


async def three_versions(client: httpx.AsyncClient, admin: dict[str, str]) -> set[str]:
    """TST-POL-20 v1 (then superseded by v2) and TST-POL-21 v1: two active versions."""
    await add(client, admin, "TST-POL-20", "1.0")
    active = {
        await add(client, admin, "TST-POL-20", "2.0"),
        await add(client, admin, "TST-POL-21", "1.0"),
    }
    client.app.state.enqueued.clear()  # type: ignore[attr-defined]
    return active


async def test_admin_requeues_only_active_versions(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    active = await three_versions(client, admin)
    r = await client.post(URL, headers=admin)
    assert r.status_code == 202 and r.json() == {"queued": 2}
    assert {str(v) for v in client.app.state.enqueued} == active  # type: ignore[attr-defined]
    with sync_session() as db:
        for vid in active:
            v = db.get(DocumentVersion, uuid.UUID(vid))
            assert v is not None and (v.status, v.ingest_status) == ("active", "pending")
        events = db.scalars(
            select(AuditEvent).where(AuditEvent.action == "knowledge_base.reprocess_all")
        ).all()
        assert len(events) == 1
        assert events[0].after == {"queued": 2, "chunk_max_tokens": 450, "chunk_overlap_tokens": 60}


async def test_pressing_twice_requeues_again(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    await three_versions(client, admin)
    assert (await client.post(URL, headers=admin)).json() == {"queued": 2}
    second = await client.post(URL, headers=admin)
    assert second.status_code == 202 and second.json() == {"queued": 2}
    with sync_session() as db:
        events = db.scalars(
            select(AuditEvent).where(AuditEvent.action == "knowledge_base.reprocess_all")
        ).all()
        assert len(events) == 2


async def test_roles(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    assert (await client.post(URL, headers=auth_headers(Role.AGENT))).status_code == 403
    app_settings.override(app_settings.load({"access": {"knowledge_base": {"reviewer": "edit"}}}))
    assert (await client.post(URL, headers=auth_headers(Role.REVIEWER))).status_code == 202
