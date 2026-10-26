"""Settings → Patterns API: read, save (with taxonomy and speed checks), test, recompute."""

import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy import select

import app_settings
from complaint_processing.detectors import detect_signals
from database.models import AuditEvent, Complaint, Role
from database.session import sync_session
from src.api.routes import patterns as patterns_routes

pytestmark = pytest.mark.db
URL = "/api/v1/settings/patterns"


def _phrase(text: str) -> dict[str, str]:
    return {"text": text, "mode": "phrase"}


async def _current(client: httpx.AsyncClient, admin: dict[str, str]) -> dict[str, Any]:
    r = await client.get(URL, headers=admin)
    assert r.status_code == 200, r.text
    data: dict[str, Any] = r.json()
    return data


async def _save(
    client: httpx.AsyncClient, admin: dict[str, str], change: Callable[[dict[str, Any]], None]
) -> httpx.Response:
    current = await _current(client, admin)
    patterns = current["patterns"]
    change(patterns)
    return await client.put(
        URL, headers=admin, json={"version": current["version"], "patterns": patterns}
    )


def _add_fire(p: dict[str, Any]) -> None:
    p["signals"]["safety_hazard"].append(_phrase("caught fire"))


async def test_admin_reads_patterns(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    data = await _current(client, auth_headers(Role.ADMIN))
    assert len(data["signal_descriptions"]) == 14
    assert "ISSUE_FULL_REFUND" in data["supported_by"]["refund"]
    assert data["last_recompute"] is None
    assert data["patterns"] == data["defaults"]


async def test_save_and_apply(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    r = await _save(client, admin, _add_fire)
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 1
    app_settings.reset_cache()
    assert "caught fire" in detect_signals("It caught fire")["safety_hazard"]


async def test_save_keeps_other_groups(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    general = (await client.get("/api/v1/settings", headers=admin)).json()
    body = {k: general["settings"][k] for k in ("email", "ai", "operations", "orders")}
    body["branding"] = {
        k: v for k, v in general["settings"]["branding"].items() if not k.endswith("_logo_key")
    }
    body["email"] = {**body["email"], "mailbox_check_seconds": 300}
    saved = await client.put(
        "/api/v1/settings", headers=admin, json={"version": general["version"], **body}
    )
    assert saved.status_code == 200, saved.text
    assert (await _save(client, admin, _add_fire)).status_code == 200
    app_settings.reset_cache()
    assert app_settings.runtime().email.mailbox_check_seconds == 300


async def test_unknown_subcategory_refused(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    def change(p: dict[str, Any]) -> None:
        p["classifier"]["DELIVERY"]["FOO"] = [{**_phrase("foo"), "weight": 1}]

    r = await _save(client, auth_headers(Role.ADMIN), change)
    assert r.status_code == 422
    assert r.json()["detail"] == "Classifier DELIVERY/FOO: subcategory does not exist."


async def test_stale_version_conflict(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    current = await _current(client, admin)
    assert (await _save(client, admin, _add_fire)).status_code == 200
    r = await client.put(
        URL, headers=admin, json={"version": current["version"], "patterns": current["patterns"]}
    )
    assert r.status_code == 409


async def test_slow_pattern_refused_on_save(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    def change(p: dict[str, Any]) -> None:
        p["signals"]["injury"].append({"text": "(a|aa)+", "mode": "regex"})

    r = await _save(client, auth_headers(Role.ADMIN), change)
    assert r.status_code == 422
    assert r.json()["detail"] == "Patterns are too slow: injury"


async def test_text_test_endpoint(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    draft = (await _current(client, admin))["patterns"]
    _add_fire(draft)
    r = await client.post(
        f"{URL}/test", headers=admin, json={"draft": draft, "text": "It caught fire"}
    )
    assert r.status_code == 200, r.text
    assert "caught fire" in r.json()["draft"]["signals"]["safety_hazard"]
    assert "caught fire" not in r.json()["saved"]["signals"].get("safety_hazard", [])
    too_long = await client.post(
        f"{URL}/test", headers=admin, json={"draft": draft, "text": "x" * 5001}
    )
    assert too_long.status_code == 422


async def test_dataset_check_endpoint(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    draft = (await _current(client, admin))["patterns"]
    r = await client.post(f"{URL}/dataset-check", headers=admin, json={"draft": draft})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 536


async def test_draft_does_not_leak_into_runtime(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    draft = (await _current(client, admin))["patterns"]
    _add_fire(draft)
    await client.post(f"{URL}/test", headers=admin, json={"draft": draft, "text": "fire"})
    app_settings.reset_cache()
    assert app_settings.runtime().patterns == app_settings.defaults().patterns


async def test_recompute_task(
    client: httpx.AsyncClient,
    auth_headers: Callable[[Role], dict[str, str]],
    complaint_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app_settings.tasks import recompute_signals

    admin = auth_headers(Role.ADMIN)
    queued: list[str | None] = []
    monkeypatch.setattr(patterns_routes, "enqueue_recompute", queued.append)

    def change(p: dict[str, Any]) -> None:
        p["signals"]["safety_hazard"].append(_phrase("late laptop delivery"))

    assert (await _save(client, admin, change)).status_code == 200
    r = await client.post(f"{URL}/recompute-signals", headers=admin)
    assert r.status_code == 202 and r.json() == {"queued": True}
    assert len(queued) == 1

    result = recompute_signals(queued[0])
    assert result["changed"] >= 1
    with sync_session() as db:
        complaint = db.get(Complaint, complaint_id)
        assert complaint is not None
        assert "safety_hazard" in complaint.signals
        event = db.scalars(
            select(AuditEvent).where(AuditEvent.action == "patterns.signals_recomputed")
        ).one()
        assert event.after == result
    last = (await _current(client, admin))["last_recompute"]
    assert last["changed"] == result["changed"] and last["total"] == result["total"]


async def test_staff_forbidden(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    agent = auth_headers(Role.AGENT)
    assert (await client.get(URL, headers=agent)).status_code == 403
    assert (await client.put(URL, headers=agent, json={})).status_code == 403
    for path in ("/test", "/dataset-check", "/recompute-signals"):
        assert (await client.post(URL + path, headers=agent, json={})).status_code == 403
