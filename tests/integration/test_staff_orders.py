"""Staff move orders by hand, which pauses automation; returns are approved or refused."""

from collections.abc import Callable
from datetime import date, timedelta

import httpx
import pytest

from database.models import Role, User
from tests.fixtures.shop import place_order, shopper

pytestmark = pytest.mark.db


async def act(
    client: httpx.AsyncClient, headers: dict[str, str], ref: str, **body: object
) -> httpx.Response:
    return await client.post(f"/api/v1/admin/orders/{ref}/actions", headers=headers, json=body)


async def test_staff_walk_an_order_to_a_late_delivery(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str],
    auth_headers: Callable[[Role], dict[str, str]],
) -> None:  # fmt: skip
    staff = auth_headers(Role.AGENT)
    ref = (await place_order(client, shopper(create_user, make_token)))["order_ref"]
    for _ in range(3):
        assert (await act(client, staff, ref, action="advance")).status_code == 200
    delayed = await act(
        client, staff, ref, action="delay", new_date=str(date.today() + timedelta(days=20))
    )
    assert delayed.status_code == 200
    done = (await act(client, staff, ref, action="advance", days_late=3)).json()
    assert done["stage"] == "delivered" and done["manual_hold"] is True
    detail = (await client.get(f"/api/v1/admin/orders/{ref}", headers=staff)).json()
    assert [e["stage"] for e in detail["events"]][-1] == "delivered"
    assert "3 business days late" in detail["events"][-1]["note"]


async def test_returns_and_illegal_actions(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str],
    auth_headers: Callable[[Role], dict[str, str]],
) -> None:  # fmt: skip
    staff, me = auth_headers(Role.AGENT), shopper(create_user, make_token)
    ref = (await place_order(client, me))["order_ref"]
    assert (await act(client, staff, ref, action="approve_return")).status_code == 409
    for _ in range(4):
        await act(client, staff, ref, action="advance")
    await client.post(
        f"/api/v1/orders/{ref}/return", headers=me, json={"reason": "The earcup rattles loudly."}
    )
    listed = (await client.get("/api/v1/admin/orders?needs_action=true", headers=staff)).json()
    assert [o["order_ref"] for o in listed] == [ref]
    assert (await act(client, staff, ref, action="approve_return")).json()["stage"] == "returned"


async def test_customers_cannot_use_the_staff_api(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    me = shopper(create_user, make_token)
    ref = (await place_order(client, me))["order_ref"]
    assert (await client.get("/api/v1/admin/orders", headers=me)).status_code == 403
    assert (await act(client, me, ref, action="advance")).status_code == 403
