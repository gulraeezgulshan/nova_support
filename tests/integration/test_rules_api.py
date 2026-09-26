from collections.abc import Callable
from typing import Any

import httpx
import pytest

from database.models import Role

pytestmark = pytest.mark.db

NEW_RULE: dict[str, Any] = {
    "rule_id": "ESC-099",
    "rule_type": "escalation",
    "description": "Complaints mentioning a regulator and over USD 200 go to compliance",
    "condition": "legal_threat and order_amount > 200",
    "supporting_departments": ["PRIVACY_COMPLIANCE"],
    "urgency": "High",
    "priority": "P1",
    "escalation_level": 4,
    "required_actions": ["ESCALATE_TO_COMPLIANCE"],
    "prohibited_actions": ["DISCUSS_LIABILITY"],
    "policy_refs": ["CPL-GDL-01#3"],
    "follow_up_type": "ESCALATION_ACKNOWLEDGEMENT",
    "follow_up_hours": 24,
}


async def test_staff_read_the_matrix_and_fact_catalogue(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    headers = auth_headers(Role.AGENT)
    rules = (await client.get("/api/v1/rules", headers=headers)).json()
    assert len(rules) >= 100
    facts = (await client.get("/api/v1/rules/facts", headers=headers)).json()
    assert {"safety_hazard", "days_late"} <= {f["name"] for f in facts}


async def test_admin_adds_a_rule_at_runtime(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    created = await client.post("/api/v1/rules", json=NEW_RULE, headers=admin)
    assert created.status_code == 201, created.text
    assert created.json()["version"] == 1

    changed = {**NEW_RULE, "condition": "legal_threat and order_amount > 100"}
    updated = await client.put("/api/v1/rules/ESC-099", json=changed, headers=admin)
    assert updated.json()["version"] == 2

    duplicate = await client.post("/api/v1/rules", json=NEW_RULE, headers=admin)
    assert duplicate.status_code == 409


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"condition": "legal_threat and __import__('os')"}, "not allowed"),
        ({"condition": "legal_thread"}, "Unknown fact"),
        ({"required_actions": ["SEND_FLOWERS"]}, "unknown action code"),
        ({"department": "MARKETING"}, "unknown department"),
        ({"policy_refs": ["CPL-GDL-01"]}, "policy references must look like"),
        ({"priority": "P9"}, "must be one of"),
    ],
)
async def test_invalid_rules_are_rejected(
    client: httpx.AsyncClient,
    auth_headers: Callable[[Role], dict[str, str]],
    change: dict[str, Any],
    message: str,
) -> None:
    response = await client.post(
        "/api/v1/rules", json={**NEW_RULE, **change}, headers=auth_headers(Role.ADMIN)
    )
    assert response.status_code == 422
    assert message in response.json()["detail"]


async def test_non_admins_cannot_change_rules(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    response = await client.post("/api/v1/rules", json=NEW_RULE, headers=auth_headers(Role.MANAGER))
    assert response.status_code == 403


async def test_matrix_exports_as_csv(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    response = await client.get("/api/v1/rules/export.csv", headers=auth_headers(Role.MANAGER))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("rule_id,rule_type,category")
    assert len(lines) > 100
