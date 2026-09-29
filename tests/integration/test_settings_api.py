"""Settings API: admin only, version check, provider keys, no secrets."""

from collections.abc import Callable

import httpx
import pytest

from database.models import Role

pytestmark = pytest.mark.db
URL = "/api/v1/settings"


def body(current: dict, **group_changes: dict) -> dict:  # type: ignore[type-arg]
    s = current["settings"]
    update = {
        g: {**s[g], **group_changes.get(g, {})} for g in ("email", "ai", "operations", "orders")
    }
    branding = {k: v for k, v in s["branding"].items() if not k.endswith("_logo_key")}
    return {
        "version": current["version"],
        **update,
        "branding": {**branding, **group_changes.get("branding", {})},
    }


async def test_admin_reads_and_saves(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    current = (await client.get(URL, headers=admin)).json()
    assert current["version"] == 0 and current["settings"]["email"]["mailbox_check_seconds"] == 60
    assert "openai" in current["suggested_models"]
    assert {f["source"] for f in current["policy_facts"]} >= {
        "WAR-POL-02",
        "REF-POL-01",
        "DEL-POL-04",
    }
    saved = await client.put(
        URL, headers=admin, json=body(current, email={"mailbox_check_seconds": 300})
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 1
    assert saved.json()["settings"]["email"]["mailbox_check_seconds"] == 300


async def test_stale_version_conflicts(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    current = (await client.get(URL, headers=admin)).json()
    assert (await client.put(URL, headers=admin, json=body(current))).status_code == 200
    assert (await client.put(URL, headers=admin, json=body(current))).status_code == 409


async def test_provider_without_key_is_refused(
    client: httpx.AsyncClient,
    auth_headers: Callable[[Role], dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    from src.core.config import get_settings

    get_settings.cache_clear()
    admin = auth_headers(Role.ADMIN)
    current = (await client.get(URL, headers=admin)).json()
    response = await client.put(
        URL,
        headers=admin,
        json=body(current, ai={"provider": "anthropic", "model": "claude-opus-5"}),
    )
    assert response.status_code == 422 and "ANTHROPIC_API_KEY" in response.text
    get_settings.cache_clear()


async def test_staff_who_are_not_admins_cannot_see_settings(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    for role in (Role.AGENT, Role.MANAGER, Role.CUSTOMER):
        assert (await client.get(URL, headers=auth_headers(role))).status_code == 403


async def test_no_secret_is_ever_returned(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    text = (await client.get(URL, headers=auth_headers(Role.ADMIN))).text.lower()
    for word in ("api_key", "password", "database_url", "redis_url", "secret"):
        assert word not in text
