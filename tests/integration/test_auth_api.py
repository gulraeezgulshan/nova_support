from collections.abc import Callable

import httpx
import pytest

from database.models import Role, User

pytestmark = pytest.mark.db


async def test_missing_token_is_401(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/me")
    assert response.status_code == 401


async def test_invalid_token_is_401(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/me", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


async def test_first_request_provisions_a_customer(
    client: httpx.AsyncClient, make_token: Callable[..., str]
) -> None:
    token = make_token("user_new", email="jane@example.test", name="Jane Doe")
    response = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert (body["email"], body["full_name"], body["role"]) == (
        "jane@example.test",
        "Jane Doe",
        "customer",
    )
    # Second call returns the same user instead of creating another.
    again = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert again.json()["id"] == body["id"]


async def test_bootstrap_email_becomes_admin(
    client: httpx.AsyncClient, make_token: Callable[..., str]
) -> None:
    token = make_token("user_founder", email="Founder@VoltHaven.test")
    response = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.json()["role"] == "admin"


async def test_customer_cannot_list_users(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    response = await client.get("/api/v1/users", headers=auth_headers(Role.CUSTOMER))
    assert response.status_code == 403


async def test_admin_changes_role_and_it_is_audited(
    client: httpx.AsyncClient,
    auth_headers: Callable[[Role], dict[str, str]],
    create_user: Callable[..., User],
) -> None:
    admin = auth_headers(Role.ADMIN)
    agent = create_user(Role.CUSTOMER)
    response = await client.patch(
        f"/api/v1/users/{agent.id}", json={"role": "agent"}, headers=admin
    )
    assert response.status_code == 200
    assert response.json()["role"] == "agent"


async def test_admin_cannot_demote_themselves(
    client: httpx.AsyncClient,
    create_user: Callable[..., User],
    make_token: Callable[..., str],
) -> None:
    admin = create_user(Role.ADMIN)
    headers = {"Authorization": f"Bearer {make_token(admin.clerk_user_id)}"}
    response = await client.patch(
        f"/api/v1/users/{admin.id}", json={"role": "customer"}, headers=headers
    )
    assert response.status_code == 409


async def test_deactivated_user_is_forbidden(
    client: httpx.AsyncClient,
    create_user: Callable[..., User],
    make_token: Callable[..., str],
    auth_headers: Callable[[Role], dict[str, str]],
) -> None:
    user = create_user(Role.AGENT)
    await client.patch(
        f"/api/v1/users/{user.id}", json={"is_active": False}, headers=auth_headers(Role.ADMIN)
    )
    response = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {make_token(user.clerk_user_id)}"}
    )
    assert response.status_code == 403
