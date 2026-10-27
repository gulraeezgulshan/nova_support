"""Settings → Customer texts API: read with placeholders and samples, save with checks."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest

import app_settings
from database.models import Role

pytestmark = pytest.mark.db
URL = "/api/v1/settings/texts"


async def _current(client: httpx.AsyncClient, admin: dict[str, str]) -> dict[str, Any]:
    r = await client.get(URL, headers=admin)
    assert r.status_code == 200, r.text
    data: dict[str, Any] = r.json()
    return data


async def _save(
    client: httpx.AsyncClient, admin: dict[str, str], change: Callable[[dict[str, Any]], None]
) -> httpx.Response:
    current = await _current(client, admin)
    texts = current["texts"]
    change(texts)
    return await client.put(
        URL, headers=admin, json={"version": current["version"], "texts": texts}
    )


def _greeting(t: dict[str, Any]) -> None:
    t["chat"]["greeting"] = "Welcome to {shop}! Which order do you mean?"


async def test_admin_reads_texts(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    data = await _current(client, auth_headers(Role.ADMIN))
    rule = data["placeholders"]["order_emails.shipped.body"]
    assert "order_ref" in rule["allowed"] and rule["required"] == []
    assert data["placeholders"]["chat.submitted"]["required"] == ["ref"]
    assert data["samples"]["shop"] == app_settings.defaults().branding.shop_name
    assert data["samples"]["name"] == "Ayesha"
    assert data["texts"] == data["defaults"]


async def test_save_and_apply(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    r = await _save(client, auth_headers(Role.ADMIN), _greeting)
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 1
    assert app_settings.runtime(fresh=True).texts.chat.greeting.startswith("Welcome to {shop}!")


async def test_save_keeps_other_groups(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    from tests.integration.test_settings_api import body

    admin = auth_headers(Role.ADMIN)
    general = (await client.get("/api/v1/settings", headers=admin)).json()
    saved = await client.put(
        "/api/v1/settings",
        headers=admin,
        json=body(general, email={"mailbox_check_seconds": 300}),
    )
    assert saved.status_code == 200, saved.text
    assert (await _save(client, admin, _greeting)).status_code == 200
    current = app_settings.runtime(fresh=True)
    assert current.email.mailbox_check_seconds == 300
    assert current.texts.chat.greeting.startswith("Welcome")


async def test_stale_version_conflict(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    current = await _current(client, admin)
    assert (await _save(client, admin, _greeting)).status_code == 200
    r = await client.put(
        URL, headers=admin, json={"version": current["version"], "texts": current["texts"]}
    )
    assert r.status_code == 409


async def test_unknown_placeholder_422(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    def change(t: dict[str, Any]) -> None:
        t["order_emails"]["shipped"]["subject"] = "Your {foo} has shipped"

    r = await _save(client, auth_headers(Role.ADMIN), change)
    assert r.status_code == 422
    assert "unknown placeholder {foo}" in r.text


async def test_staff_forbidden(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    agent = auth_headers(Role.AGENT)
    assert (await client.get(URL, headers=agent)).status_code == 403
    assert (await client.put(URL, headers=agent, json={})).status_code == 403


async def test_general_settings_leave_out_texts(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    data = (await client.get("/api/v1/settings", headers=auth_headers(Role.ADMIN))).json()
    assert "texts" not in data["settings"] and "texts" not in data["defaults"]
