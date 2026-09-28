"""Upload -> ingest -> activate -> search, end to end against a real Postgres + pgvector."""

import uuid
from collections.abc import Callable

import httpx
import pytest

from database.models import Role
from database.session import sync_session
from knowledge_base.embeddings import get_embedder
from knowledge_base.ingestion import ingest_version
from src.core.config import get_settings
from src.core.storage import get_storage
from tests.fixtures.documents import DELIVERY_HEADER, DELIVERY_SECTIONS, make_docx

pytestmark = pytest.mark.db

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def run_ingest(version_id: str) -> None:
    """What the Celery worker does, run inline."""
    with sync_session() as db:
        ingest_version(
            db,
            uuid.UUID(version_id),
            storage=get_storage(),
            embedder=get_embedder(),
            settings=get_settings(),
        )


async def upload(
    client: httpx.AsyncClient, headers: dict[str, str], data: bytes, **form: str
) -> httpx.Response:
    return await client.post(
        "/api/v1/documents/upload",
        files={"file": ("delivery-policy.docx", data, DOCX)},
        data=form,
        headers=headers,
    )


async def test_upload_ingest_and_search_active_policy(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    response = await upload(client, admin, make_docx(DELIVERY_HEADER, DELIVERY_SECTIONS))
    assert response.status_code == 202, response.text
    version = response.json()
    assert (version["ingest_status"], version["status"]) == ("pending", "draft")
    assert client.app.state.enqueued == [uuid.UUID(version["id"])]  # type: ignore[attr-defined]

    run_ingest(version["id"])

    documents = (await client.get("/api/v1/documents", headers=admin)).json()
    [document] = documents
    assert (document["doc_code"], document["title"]) == ("DEL-POL-04", "Delivery Policy")
    [stored] = document["versions"]
    assert (stored["ingest_status"], stored["status"]) == ("ready", "active")
    assert stored["chunk_count"] >= 2

    chunks = (
        await client.get(f"/api/v1/document-versions/{version['id']}/chunks", headers=admin)
    ).json()
    assert any(c["section"] == "5.2" for c in chunks)
    assert chunks[0]["chunk_code"] == "DEL-POL-04@1.0#001"

    results = (
        await client.get(
            "/api/v1/knowledge-base/search",
            params={"q": "late delivery store credit compensation"},
            headers=auth_headers(Role.AGENT),
        )
    ).json()
    assert results[0]["doc_code"] == "DEL-POL-04"
    assert results[0]["section"] == "5.2"


async def test_new_version_supersedes_old_and_only_active_is_searchable(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    v1 = (await upload(client, admin, make_docx(DELIVERY_HEADER, DELIVERY_SECTIONS))).json()
    run_ingest(v1["id"])

    revised_sections = [
        (
            "5.2 Late Delivery Compensation",
            ["Orders more than 3 business days late receive a 15% store credit."],
        )
    ]
    v2_bytes = make_docx({**DELIVERY_HEADER, "Version": "2.0"}, revised_sections)
    v2 = (await upload(client, admin, v2_bytes)).json()
    run_ingest(v2["id"])

    [document] = (await client.get("/api/v1/documents", headers=admin)).json()
    statuses = {v["version"]: v["status"] for v in document["versions"]}
    assert statuses == {"1.0": "superseded", "2.0": "active"}

    results = (
        await client.get(
            "/api/v1/knowledge-base/search",
            params={"q": "late delivery store credit"},
            headers=admin,
        )
    ).json()
    assert {r["version"] for r in results} == {"2.0"}


async def test_duplicate_file_and_duplicate_version_are_rejected(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    data = make_docx(DELIVERY_HEADER, DELIVERY_SECTIONS)
    assert (await upload(client, admin, data)).status_code == 202
    assert (await upload(client, admin, data)).status_code == 409

    same_version_new_text = make_docx(DELIVERY_HEADER, [("1 Purpose", ["Different text."])])
    response = await upload(client, admin, same_version_new_text)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


async def test_invalid_metadata_returns_all_issues(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    no_header = make_docx({}, DELIVERY_SECTIONS)
    response = await upload(client, auth_headers(Role.ADMIN), no_header, doc_type="memo")
    assert response.status_code == 422
    issues = response.json()["issues"]
    assert any("doc_code" in issue for issue in issues)
    assert any("effective_date" in issue for issue in issues)


async def test_non_admin_cannot_upload(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    data = make_docx(DELIVERY_HEADER, DELIVERY_SECTIONS)
    assert (await upload(client, auth_headers(Role.AGENT), data)).status_code == 403


async def test_customer_cannot_read_knowledge_base(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    response = await client.get("/api/v1/documents", headers=auth_headers(Role.CUSTOMER))
    assert response.status_code == 403


async def test_staff_can_open_the_original_document(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    data = make_docx(DELIVERY_HEADER, DELIVERY_SECTIONS)
    version = (await upload(client, admin, data)).json()
    url = f"/api/v1/document-versions/{version['id']}/file"

    response = await client.get(url, headers=auth_headers(Role.AGENT))
    assert response.status_code == 200 and response.content == data  # the exact upload
    assert response.headers["content-type"].startswith(DOCX)
    assert response.headers["content-disposition"] == 'attachment; filename="delivery-policy.docx"'
    assert response.headers["x-content-type-options"] == "nosniff"

    assert (await client.get(url, headers=auth_headers(Role.CUSTOMER))).status_code == 403
    missing = f"/api/v1/document-versions/{uuid.uuid4()}/file"
    assert (await client.get(missing, headers=admin)).status_code == 404


def test_pdfs_and_text_open_in_the_browser_other_files_download() -> None:
    from src.api.routes.documents import content_disposition

    assert content_disposition("application/pdf", "Refund policy.pdf") == (
        'inline; filename="Refund_policy.pdf"'
    )
    assert content_disposition("text/markdown", "faq.md").startswith("inline;")
    assert content_disposition(DOCX, 'x"; evil.docx').startswith("attachment;")
    assert '"' not in content_disposition(DOCX, 'x"; evil.docx')[22:-1]
