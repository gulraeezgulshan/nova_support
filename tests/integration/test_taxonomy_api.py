from collections.abc import Callable

import httpx
import pytest

from database.models import Role

pytestmark = pytest.mark.db


async def test_seeded_taxonomy_is_listed(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    headers = auth_headers(Role.AGENT)
    categories = (await client.get("/api/v1/taxonomy/categories", headers=headers)).json()
    departments = (await client.get("/api/v1/taxonomy/departments", headers=headers)).json()
    assert len(categories) >= 10
    assert sum(len(c["subcategories"]) for c in categories) >= 20
    assert len(departments) >= 8


async def test_admin_adds_category_and_subcategory_at_runtime(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    created = await client.post(
        "/api/v1/taxonomy/categories",
        json={"code": "SUSTAINABILITY", "name": "Sustainability"},
        headers=admin,
    )
    assert created.status_code == 201
    category_id = created.json()["id"]

    sub = await client.post(
        f"/api/v1/taxonomy/categories/{category_id}/subcategories",
        json={"code": "EXCESS_PACKAGING", "name": "Excess packaging"},
        headers=admin,
    )
    assert sub.status_code == 201

    listed = (await client.get("/api/v1/taxonomy/categories", headers=admin)).json()
    new = next(c for c in listed if c["code"] == "SUSTAINABILITY")
    assert [s["code"] for s in new["subcategories"]] == ["EXCESS_PACKAGING"]


async def test_duplicate_category_code_is_409(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    response = await client.post(
        "/api/v1/taxonomy/categories",
        json={"code": "BILLING", "name": "Billing again"},
        headers=auth_headers(Role.ADMIN),
    )
    assert response.status_code == 409


async def test_only_admins_change_taxonomy(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    response = await client.post(
        "/api/v1/taxonomy/departments",
        json={"code": "LEGAL", "name": "Legal"},
        headers=auth_headers(Role.MANAGER),
    )
    assert response.status_code == 403


async def test_admin_changes_sla_threshold(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    slas = (await client.get("/api/v1/taxonomy/sla-policies", headers=admin)).json()
    p0 = next(s for s in slas if s["priority"] == "P0")
    response = await client.patch(
        f"/api/v1/taxonomy/sla-policies/{p0['id']}",
        json={"resolution_minutes": 180},
        headers=admin,
    )
    assert response.status_code == 200
    assert response.json()["resolution_minutes"] == 180
