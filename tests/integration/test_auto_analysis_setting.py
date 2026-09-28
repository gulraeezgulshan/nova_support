"""'Analyse new complaints automatically' off: intake queues nothing; a manual re-run still does."""

from collections.abc import Callable

import httpx
import pytest

from database.models import Role
from tests.fixtures.settings import use_settings

pytestmark = pytest.mark.db

COMPLAINT = {
    "title": "Charger stopped working",
    "description": "My VoltCharge 65W charger stopped working after two days of normal use.",
    "requested_resolution": "A replacement",
}


async def test_auto_analysis_off_queues_nothing_until_asked(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    use_settings(ai={"auto_analysis": False})
    customer = auth_headers(Role.CUSTOMER)
    created = await client.post("/api/v1/complaints", json=COMPLAINT, headers=customer)
    assert created.status_code == 201, created.text
    assert client.app.state.analyses == []  # type: ignore[attr-defined]
    ref = created.json()["complaint_ref"]
    rerun = await client.post(f"/api/v1/complaints/{ref}/analyze", headers=auth_headers(Role.AGENT))
    assert rerun.status_code == 202
    assert len(client.app.state.analyses) == 1  # type: ignore[attr-defined]
