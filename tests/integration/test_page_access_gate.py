"""Page access gate: the default matrix gives exactly today's access, and the matrix is enforced."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from fastapi.routing import APIRoute

import app_settings
from app_settings.access import PAGE_KEYS
from database.models import Role
from security.dependencies import NO_ACCESS

pytestmark = pytest.mark.db

ALL = {"agent", "reviewer", "manager", "admin"}
INSIGHT = {"reviewer", "manager", "admin"}
MGR = {"manager", "admin"}
ADMIN = {"admin"}
ID = "00000000-0000-0000-0000-000000000001"
C = "/complaints/CMP-999999"
V = f"/document-versions/{ID}"
P = "/admin/products/VH-NONE"

# Today's access, recorded literally (not derived from the new code): (method, path, roles).
ROUTES: list[tuple[str, str, set[str]]] = [
    ("GET", "/dashboard/agent", ALL),
    ("GET", f"{C}/analysis", ALL),
    ("POST", f"{C}/analyze", ALL),
    ("GET", f"{C}/validation", ALL),
    ("POST", f"{C}/validate", ALL),
    ("GET", f"{C}/decisions", ALL),
    ("PATCH", f"{C}/status", ALL),
    ("GET", f"{C}/chat", ALL),
    ("GET", "/review-queue", INSIGHT),
    ("POST", f"{C}/review", INSIGHT),
    ("GET", "/enquiries", ALL),
    ("PATCH", "/enquiries/ENQ-999999", ALL),
    ("POST", "/enquiries/ENQ-999999/convert", ALL),
    ("GET", "/mailbox", ALL),
    ("GET", "/mailbox/inbound", ALL),
    ("GET", "/mailbox/outbound", ALL),
    ("POST", "/mailbox/process", ALL),
    ("GET", "/admin/orders", ALL),
    ("GET", "/admin/orders/ORD-999999", ALL),
    ("POST", "/admin/orders/ORD-999999/actions", ALL),
    ("GET", "/imports", MGR),
    ("GET", f"/imports/{ID}", MGR),
    ("GET", f"/imports/{ID}/result.csv", MGR),
    ("GET", "/imports/template.csv", MGR),
    ("GET", "/imports/template.xlsx", MGR),
    ("POST", "/imports/preview", MGR),
    ("POST", f"/imports/{ID}/run", MGR),
    ("GET", "/analytics", INSIGHT),
    ("GET", "/dashboard/admin", INSIGHT),
    ("GET", "/reports", INSIGHT),
    ("GET", "/reports/x", INSIGHT),
    ("GET", "/reports/x/export", INSIGHT),
    ("GET", "/documents", ALL),
    ("GET", "/documents/types", ALL),
    ("GET", f"/documents/{ID}", ALL),
    ("GET", f"{V}/file", ALL),
    ("GET", f"{V}/chunks", ALL),
    ("GET", "/knowledge-base/search?q=late", ALL),
    ("POST", "/documents/upload", ADMIN),
    ("POST", f"{V}/activate", ADMIN),
    ("POST", f"{V}/retire", ADMIN),
    ("POST", f"{V}/reprocess", ADMIN),
    ("GET", "/taxonomy/sla-policies", ALL),
    ("POST", "/taxonomy/departments", ADMIN),
    ("PATCH", f"/taxonomy/departments/{ID}", ADMIN),
    ("POST", "/taxonomy/categories", ADMIN),
    ("PATCH", f"/taxonomy/categories/{ID}", ADMIN),
    ("POST", f"/taxonomy/categories/{ID}/subcategories", ADMIN),
    ("PATCH", f"/taxonomy/sla-policies/{ID}", ADMIN),
    ("GET", "/rules", ALL),
    ("GET", "/rules/facts", ALL),
    ("GET", "/rules/export.csv", ALL),
    ("POST", "/rules", ADMIN),
    ("PUT", "/rules/DEL-001", ADMIN),
    ("GET", "/admin/products", ADMIN),
    ("POST", "/admin/products", ADMIN),
    ("PATCH", P, ADMIN),
    ("POST", f"{P}/images", ADMIN),
    ("PUT", f"{P}/images/order", ADMIN),
    ("DELETE", f"{P}/images/{ID}", ADMIN),
    ("GET", "/users", MGR),
    ("PATCH", f"/users/{ID}", ADMIN),
    ("GET", "/settings", ADMIN),
    ("PUT", "/settings", ADMIN),
    ("GET", "/taxonomy/departments", ALL | {"customer"}),
    ("GET", "/taxonomy/categories", ALL | {"customer"}),
    ("GET", "/taxonomy/vocabulary", ALL),
]


async def call(client: httpx.AsyncClient, method: str, path: str, headers: dict[str, str]) -> int:
    body: dict[str, object] | None = {} if method in ("POST", "PUT", "PATCH") else None
    r = await client.request(method, "/api/v1" + path, headers=headers, json=body)
    return r.status_code


@pytest.mark.parametrize("role", ["customer", "agent", "reviewer", "manager", "admin"])
async def test_default_access_matches_today(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]], role: str
) -> None:
    headers = auth_headers(Role(role))
    wrong = []
    for method, path, allowed in ROUTES:
        status = await call(client, method, path, headers)
        if (status != 403) != (role in allowed):
            wrong.append((method, path, status))
    assert wrong == []


# ------------------------------------------------------------------ the matrix is enforced


def matrix(**pages: dict[str, str]) -> "app_settings.RuntimeSettings":
    """Default settings with these pages changed, e.g. matrix(analytics={"agent": "view"})."""
    return app_settings.load({"access": pages})


async def test_matrix_grants_and_removes(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    agent = auth_headers(Role.AGENT)
    app_settings.override(matrix(analytics={"agent": "view"}, rules={"agent": "none"}))
    assert (await client.get("/api/v1/analytics", headers=agent)).status_code == 200
    r = await client.get("/api/v1/rules", headers=agent)
    assert r.status_code == 403 and r.json()["detail"] == NO_ACCESS


async def test_view_is_not_edit(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    app_settings.override(matrix(orders={"agent": "view"}))
    agent = auth_headers(Role.AGENT)
    assert (await client.get("/api/v1/admin/orders", headers=agent)).status_code == 200
    actions = "/api/v1/admin/orders/ORD-1/actions"
    assert (await client.post(actions, headers=agent, json={})).status_code == 403


async def test_admin_cannot_be_locked_out_and_customer_cannot_be_let_in(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    nobody = {"agent": "none", "reviewer": "none", "manager": "none"}
    app_settings.override(matrix(**dict.fromkeys(PAGE_KEYS, nobody)))
    assert (await client.get("/api/v1/rules", headers=auth_headers(Role.ADMIN))).status_code == 200
    customer = auth_headers(Role.CUSTOMER)
    assert (await client.get("/api/v1/rules", headers=customer)).status_code == 403


async def test_mixed_endpoints_gate_only_staff(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    app_settings.override(matrix(complaints={"agent": "none"}))
    agent, customer = auth_headers(Role.AGENT), auth_headers(Role.CUSTOMER)
    assert (await client.get("/api/v1/complaints", headers=agent)).status_code == 403
    assert (await client.get("/api/v1/complaints", headers=customer)).status_code == 200
    assert (await client.get("/api/v1/complaints/CMP-999999", headers=agent)).status_code == 403
    attachments = "/api/v1/complaints/CMP-999999/attachments"
    assert (await client.get(attachments, headers=agent)).status_code == 403


async def test_mixed_order_endpoints_gate_only_staff(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    app_settings.override(matrix(orders={"agent": "none"}))
    agent = auth_headers(Role.AGENT)
    for path in ("/orders/ORD-999999/events", "/orders/ORD-999999/receipt.pdf"):
        assert (await client.get("/api/v1" + path, headers=agent)).status_code == 403


async def test_shared_lookups_stay_open(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    app_settings.override(matrix(taxonomy={"agent": "none"}))
    agent = auth_headers(Role.AGENT)
    for p in ("/taxonomy/departments", "/taxonomy/categories", "/taxonomy/vocabulary"):
        assert (await client.get("/api/v1" + p, headers=agent)).status_code == 200


def _routes(routes: list[Any], prefix: str = "") -> list[tuple[str, APIRoute]]:
    found: list[tuple[str, APIRoute]] = []
    for r in routes:
        if isinstance(r, APIRoute):
            found.append((prefix + r.path, r))
            continue
        sub = getattr(r, "router", None) or getattr(r, "original_router", None)
        if sub is not None:
            found += _routes(sub.routes, prefix + (getattr(r, "prefix", "") or ""))
    return found


def _role_sets(dependant: Any) -> list[frozenset[Role]]:
    sets: list[frozenset[Role]] = []
    for d in dependant.dependencies:
        for cell in getattr(d.call, "__closure__", None) or ():
            if isinstance(cell.cell_contents, frozenset):
                sets.append(cell.cell_contents)
        sets += _role_sets(d)
    return sets


def test_every_staff_route_is_gated() -> None:
    """A route may use require_roles only for Administrator-only or customer-only endpoints."""
    from src.main import create_app

    loose = [
        f"{','.join(sorted(r.methods or ()))} {path}"
        for path, r in _routes(create_app().routes)
        for roles in _role_sets(r.dependant)
        if roles not in ({Role.ADMIN}, {Role.CUSTOMER})
    ]
    assert loose == []
