"""Supporting documents on complaints: who may add, see and download them."""

from collections.abc import Callable

import httpx
import pytest
from sqlalchemy import select

from database.models import AuditEvent, ComplaintAttachment, Role, User
from database.session import sync_session

pytestmark = pytest.mark.db

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
PDF = b"%PDF-1.7\n" + b"0" * 64


async def file_complaint(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    body = {
        "title": "Cracked tablet screen",
        "description": "My tablet arrived with a cracked screen and the box was crushed badly.",
    }
    response = await client.post("/api/v1/complaints", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return str(response.json()["complaint_ref"])


async def attach(
    client: httpx.AsyncClient, ref: str, headers: dict[str, str], name: str, data: bytes
) -> httpx.Response:
    return await client.post(
        f"/api/v1/complaints/{ref}/attachments",
        headers=headers,
        files={"file": (name, data, "application/octet-stream")},
    )


@pytest.fixture
def owner(create_user: Callable[..., User], make_token: Callable[..., str]) -> dict[str, str]:
    user = create_user(Role.CUSTOMER, email="owner@example.test")
    return {"Authorization": f"Bearer {make_token(user.clerk_user_id)}"}


async def test_owner_attaches_and_downloads(
    client: httpx.AsyncClient, owner: dict[str, str]
) -> None:
    ref = await file_complaint(client, owner)
    added = await attach(client, ref, owner, "damage.png", PNG)
    assert added.status_code == 201, added.text
    body = added.json()
    assert body["media_type"] == "image/png" and body["source"] == "customer"
    listed = (await client.get(f"/api/v1/complaints/{ref}/attachments", headers=owner)).json()
    assert [a["id"] for a in listed] == [body["id"]]
    download = await client.get(f"/api/v1/complaints/{ref}/attachments/{body['id']}", headers=owner)
    assert download.content == PNG
    assert download.headers["content-type"] == "image/png"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["content-disposition"].startswith("attachment;")


async def test_other_customers_cannot_see_or_add(
    client: httpx.AsyncClient,
    owner: dict[str, str],
    auth_headers: Callable[[Role], dict[str, str]],
) -> None:
    ref = await file_complaint(client, owner)
    added = (await attach(client, ref, owner, "r.pdf", PDF)).json()
    one = f"/api/v1/complaints/{ref}/attachments/{added['id']}"
    stranger = auth_headers(Role.CUSTOMER)
    assert (
        await client.get(f"/api/v1/complaints/{ref}/attachments", headers=stranger)
    ).status_code == 404
    assert (await client.get(one, headers=stranger)).status_code == 404
    assert (await attach(client, ref, stranger, "x.png", PNG)).status_code == 404
    staff = auth_headers(Role.AGENT)
    assert (await client.get(one, headers=staff)).status_code == 200
    assert (await client.delete(one, headers=owner)).status_code == 403
    assert (await client.delete(one, headers=staff)).status_code == 204
    assert (await client.get(one, headers=staff)).status_code == 404


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        ("fake.png", b"MZ\x90\x00not an image", "Only photos"),
        ("empty.png", b"", "empty"),
        ("big.pdf", b"%PDF-" + b"0" * (5 * 1024 * 1024), "5 MB"),
    ],
    ids=["disguised", "empty", "too-big"],
)
async def test_bad_files_are_refused(
    client: httpx.AsyncClient, owner: dict[str, str], name: str, data: bytes, message: str
) -> None:
    ref = await file_complaint(client, owner)
    response = await attach(client, ref, owner, name, data)
    assert response.status_code == 422 and message in response.json()["detail"]


async def test_at_most_five_and_names_are_safe(
    client: httpx.AsyncClient, owner: dict[str, str]
) -> None:
    ref = await file_complaint(client, owner)
    for i in range(5):
        response = await attach(client, ref, owner, f"../../etc/passwd{i}.png", PNG)
        assert response.status_code == 201
    sixth = await attach(client, ref, owner, "six.png", PNG)
    assert sixth.status_code == 422 and "at most 5" in sixth.json()["detail"]
    nameless = await client.get(f"/api/v1/complaints/{ref}/attachments", headers=owner)
    assert len(nameless.json()) == 5
    with sync_session() as db:
        stored = db.scalars(select(ComplaintAttachment)).all()
        assert all("/" not in a.filename and ".." not in a.filename for a in stored)
        assert all(a.storage_key.startswith(f"complaints/{a.complaint_id}/") for a in stored)
        assert db.scalar(select(AuditEvent).where(AuditEvent.action == "attachment.added"))
