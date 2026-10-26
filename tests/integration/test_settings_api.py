"""Settings API: admin only, version check, provider keys, no secrets."""

from collections.abc import Callable

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app_settings
from database.models import Role, User

pytestmark = pytest.mark.db
URL = "/api/v1/settings"


def body(current: dict, **group_changes: dict) -> dict:  # type: ignore[type-arg]
    s = current["settings"]
    update = {
        g: {**s[g], **group_changes.get(g, {})}
        for g in ("email", "ai", "operations", "orders", "knowledge_base", "validation")
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


async def test_settings_save_keeps_the_access_matrix(
    client: httpx.AsyncClient,
    auth_headers: Callable[[Role], dict[str, str]],
    async_db: AsyncSession,
) -> None:
    admin_headers = auth_headers(Role.ADMIN)
    admin = (await async_db.scalars(select(User).where(User.role == Role.ADMIN))).one()
    changed = app_settings.load({"access": {"analytics": {"agent": "view"}}})
    await app_settings.save(
        async_db,
        changed,
        actor=admin,
        expected_version=None,
        action="access.updated",
        audit_group="access",
    )
    current = (await client.get(URL, headers=admin_headers)).json()
    saved = await client.put(
        URL, headers=admin_headers, json=body(current, email={"mailbox_check_seconds": 300})
    )
    assert saved.status_code == 200
    row = await app_settings.current_row(async_db)
    assert row is not None
    await async_db.refresh(row)
    stored = app_settings.load(row.data)
    assert stored.access.analytics.agent == "view"
    assert stored.email.mailbox_check_seconds == 300


# ------------------------------------------------------------------ knowledge base settings


def _seed_document(doc_code: str, doc_type: str) -> None:
    from database.models import Document
    from database.session import sync_session

    with sync_session() as db:
        db.add(Document(doc_code=doc_code, title=f"{doc_code} title", doc_type=doc_type))


async def test_admin_saves_knowledge_base_values(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    current = (await client.get(URL, headers=admin)).json()
    assert current["defaults"]["knowledge_base"]["chunk_max_tokens"] == 450
    changes = {"chunk_max_tokens": 300, "chunk_overlap_tokens": 40}
    saved = await client.put(URL, headers=admin, json=body(current, knowledge_base=changes))
    assert saved.status_code == 200
    kb = saved.json()["settings"]["knowledge_base"]
    assert (kb["chunk_max_tokens"], kb["chunk_overlap_tokens"]) == (300, 40)
    assert saved.json()["defaults"]["knowledge_base"]["chunk_max_tokens"] == 450


async def test_removing_a_type_in_use_is_refused(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    _seed_document("FAQ-GEN-01", "faq")
    admin = auth_headers(Role.ADMIN)
    current = (await client.get(URL, headers=admin)).json()
    types = [
        t for t in current["settings"]["knowledge_base"]["document_types"] if t["code"] != "faq"
    ]
    r = await client.put(
        URL, headers=admin, json=body(current, knowledge_base={"document_types": types})
    )
    assert r.status_code == 422
    assert "faq is used by 1 documents (FAQ-GEN-01); retire or re-type them first." in r.text


async def test_removing_an_unused_type_is_allowed(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    current = (await client.get(URL, headers=admin)).json()
    types = [
        t for t in current["settings"]["knowledge_base"]["document_types"] if t["code"] != "sla"
    ]
    r = await client.put(
        URL, headers=admin, json=body(current, knowledge_base={"document_types": types})
    )
    assert r.status_code == 200
    assert "sla" not in {
        t["code"] for t in r.json()["settings"]["knowledge_base"]["document_types"]
    }


async def test_invalid_knowledge_base_value_is_rejected(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    current = (await client.get(URL, headers=admin)).json()
    r = await client.put(
        URL, headers=admin, json=body(current, knowledge_base={"chunk_max_tokens": 999})
    )
    assert r.status_code == 422


# ------------------------------------------------------------------ validation settings


async def test_admin_saves_validation_values(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    current = (await client.get(URL, headers=admin)).json()
    assert {"safety_hazard", "prompt_injection"} <= set(current["risk_signals"])
    assert len(current["risk_signals"]) == 14
    comp = current["settings"]["validation"]["compensation"]
    comp["store_credit"]["max_amount"] = 75
    saved = await client.put(
        URL, headers=admin, json=body(current, validation={"compensation": comp})
    )
    assert saved.status_code == 200, saved.text
    assert (
        saved.json()["settings"]["validation"]["compensation"]["store_credit"]["max_amount"] == 75
    )
    assert (
        saved.json()["defaults"]["validation"]["compensation"]["store_credit"]["max_amount"] == 50
    )


async def test_unknown_category_needing_an_order_is_refused(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    current = (await client.get(URL, headers=admin)).json()
    r = await client.put(
        URL, headers=admin, json=body(current, validation={"orders_required_for": ["FOO"]})
    )
    assert r.status_code == 422
    assert "Needs an order: category FOO does not exist." in r.text


async def test_boost_subcategory_outside_category_is_refused(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    current = (await client.get(URL, headers=admin)).json()
    boosts = current["settings"]["validation"]["signal_boosts"]
    boosts["safety_hazard"] = {
        "category": "BILLING",
        "subcategory": "OVERHEATING_BATTERY",
        "weight": 3,
    }
    r = await client.put(
        URL, headers=admin, json=body(current, validation={"signal_boosts": boosts})
    )
    assert r.status_code == 422
    assert (
        "Signal boost safety_hazard: subcategory OVERHEATING_BATTERY is not in category BILLING."
        in r.text
    )


async def test_boost_unknown_category_is_refused(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    current = (await client.get(URL, headers=admin)).json()
    boosts = current["settings"]["validation"]["signal_boosts"]
    boosts["injury"] = {"category": "NOPE", "subcategory": "INJURY_REPORTED", "weight": 4}
    r = await client.put(
        URL, headers=admin, json=body(current, validation={"signal_boosts": boosts})
    )
    assert r.status_code == 422
    assert "Signal boost injury: category NOPE does not exist." in r.text


async def test_validation_left_out_keeps_stored_values(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    current = (await client.get(URL, headers=admin)).json()
    saved = await client.put(
        URL, headers=admin, json=body(current, validation={"classifier_confident": 5})
    )
    assert saved.status_code == 200
    again = saved.json()
    payload = {k: v for k, v in body(again).items() if k != "validation"}
    r = await client.put(URL, headers=admin, json=payload)
    assert r.status_code == 200
    assert r.json()["settings"]["validation"]["classifier_confident"] == 5


async def test_settings_leave_out_the_text_patterns(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    """Patterns have their own page and endpoint; the general settings stay small."""
    data = (await client.get(URL, headers=auth_headers(Role.ADMIN))).json()
    assert "patterns" not in data["settings"]
    assert "patterns" not in data["defaults"]
