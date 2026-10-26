"""Page access API (admin only) and the permissions every user gets on /me."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app_settings.access import EDITABLE_ROLES, PAGE_KEYS, default_access
from database.models import AuditEvent, Role
from database.session import sync_session

pytestmark = pytest.mark.db
URL = "/api/v1/access"
Headers = Callable[[Role], dict[str, str]]


def default_matrix() -> dict[str, dict[str, str]]:
    return {k: dict(v) for k, v in default_access().model_dump().items()}


async def put(client: httpx.AsyncClient, headers: dict[str, str], matrix: Any, version: int) -> Any:
    return await client.put(URL, headers=headers, json={"matrix": matrix, "version": version})


async def test_admin_reads_catalogue_and_matrix(
    client: httpx.AsyncClient, auth_headers: Headers
) -> None:
    r = await client.get(URL, headers=auth_headers(Role.ADMIN))
    assert r.status_code == 200
    body = r.json()
    assert [p["key"] for p in body["pages"]] == list(PAGE_KEYS)
    assert {p["key"] for p in body["pages"] if not p["has_edit"]} == {
        "dashboard",
        "analytics",
        "reports",
        "users",
    }
    assert body["version"] == 0 and body["matrix"] == default_matrix()
    assert body["pages"][1]["default"] == {"agent": "edit", "reviewer": "edit", "manager": "edit"}


async def test_put_applies_immediately(client: httpx.AsyncClient, auth_headers: Headers) -> None:
    admin, agent = auth_headers(Role.ADMIN), auth_headers(Role.AGENT)
    assert (await client.get("/api/v1/analytics", headers=agent)).status_code == 403
    matrix = default_matrix()
    matrix["analytics"]["agent"] = "view"
    r = await put(client, admin, matrix, 0)
    assert r.status_code == 200 and r.json()["version"] == 1
    assert (await client.get("/api/v1/analytics", headers=agent)).status_code == 200
    me = (await client.get("/api/v1/me", headers=agent)).json()
    assert me["permissions"]["analytics"] == "view"


async def test_put_is_audited_with_only_the_matrix(
    client: httpx.AsyncClient, auth_headers: Headers
) -> None:
    matrix = default_matrix()
    matrix["rules"]["manager"] = "edit"
    assert (await put(client, auth_headers(Role.ADMIN), matrix, 0)).status_code == 200
    with sync_session() as db:
        event = db.scalars(select(AuditEvent).where(AuditEvent.action == "access.updated")).one()
        assert event.before is not None and event.after is not None
        assert set(event.after) == set(PAGE_KEYS)
        assert event.before["rules"]["manager"] == "view"
        assert event.after["rules"]["manager"] == "edit"


async def test_stale_put_is_refused(client: httpx.AsyncClient, auth_headers: Headers) -> None:
    admin = auth_headers(Role.ADMIN)
    assert (await put(client, admin, default_matrix(), 0)).status_code == 200
    r = await put(client, admin, default_matrix(), 0)
    assert r.status_code == 409


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m.pop("rules"),
        lambda m: m["reports"].update(agent="edit"),
        lambda m: m["rules"].update(admin="none"),
        lambda m: m["rules"].update(customer="view"),
        lambda m: m.update(nope={r: "view" for r in EDITABLE_ROLES}),
    ],
)
async def test_invalid_put_is_rejected(
    client: httpx.AsyncClient, auth_headers: Headers, change: Callable[[dict[str, Any]], Any]
) -> None:
    matrix: dict[str, Any] = default_matrix()
    change(matrix)
    r = await put(client, auth_headers(Role.ADMIN), matrix, 0)
    assert r.status_code == 422


@pytest.mark.parametrize("role", [Role.AGENT, Role.REVIEWER, Role.MANAGER, Role.CUSTOMER])
async def test_non_admins_get_403(
    client: httpx.AsyncClient, auth_headers: Headers, role: Role
) -> None:
    headers = auth_headers(role)
    assert (await client.get(URL, headers=headers)).status_code == 403
    assert (await put(client, headers, default_matrix(), 0)).status_code == 403


async def test_access_save_keeps_other_settings(
    client: httpx.AsyncClient, auth_headers: Headers
) -> None:
    from tests.integration.test_settings_api import body as settings_body

    admin = auth_headers(Role.ADMIN)
    current = (await client.get("/api/v1/settings", headers=admin)).json()
    saved = await client.put(
        "/api/v1/settings",
        headers=admin,
        json=settings_body(current, email={"mailbox_check_seconds": 300}),
    )
    assert saved.status_code == 200
    version = (await client.get(URL, headers=admin)).json()["version"]
    assert (await put(client, admin, default_matrix(), version)).status_code == 200
    after = (await client.get("/api/v1/settings", headers=admin)).json()
    assert after["settings"]["email"]["mailbox_check_seconds"] == 300


async def test_me_permissions_per_role(client: httpx.AsyncClient, auth_headers: Headers) -> None:
    async def perms(role: Role) -> dict[str, str]:
        r = await client.get("/api/v1/me", headers=auth_headers(role))
        assert r.status_code == 200
        permissions: dict[str, str] = r.json()["permissions"]
        return permissions

    admin = await perms(Role.ADMIN)
    assert set(admin.values()) == {"edit"} and {"settings", "access"} <= set(admin)
    assert set((await perms(Role.CUSTOMER)).values()) == {"none"}
    reviewer = await perms(Role.REVIEWER)
    assert reviewer["review"] == "edit" and reviewer["imports"] == "none"
    assert reviewer["settings"] == "none" and reviewer["access"] == "none"
