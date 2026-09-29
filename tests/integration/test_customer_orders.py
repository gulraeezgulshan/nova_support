"""Customers cancel before shipping, return within 30 days, see history, get a receipt."""

from collections.abc import Callable
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import update

from database.models import Order, Role, User
from database.session import sync_session
from tests.fixtures.shop import place_order, shopper

pytestmark = pytest.mark.db


def set_order(ref: str, **values: object) -> None:
    with sync_session() as db:
        db.execute(update(Order).where(Order.order_ref == ref).values(**values))


async def test_cancel_before_shipping_only(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    me = shopper(create_user, make_token)
    ref = (await place_order(client, me))["order_ref"]
    done = await client.post(f"/api/v1/orders/{ref}/cancel", headers=me)
    assert done.status_code == 200 and done.json()["stage"] == "cancelled"
    other = (await place_order(client, me))["order_ref"]
    set_order(other, stage="shipped", status="shipped")
    assert (await client.post(f"/api/v1/orders/{other}/cancel", headers=me)).status_code == 409


async def test_return_within_the_window_with_a_reason(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    me = shopper(create_user, make_token)
    ref = (await place_order(client, me))["order_ref"]
    set_order(
        ref, stage="delivered", status="delivered", delivered_date=date.today() - timedelta(days=5)
    )
    short = await client.post(f"/api/v1/orders/{ref}/return", headers=me, json={"reason": "no"})
    assert short.status_code == 422
    ok = await client.post(f"/api/v1/orders/{ref}/return", headers=me,
                           json={"reason": "The left earcup rattles."})  # fmt: skip
    assert ok.status_code == 200 and ok.json()["stage"] == "return_requested"
    late = (await place_order(client, me))["order_ref"]
    set_order(
        late,
        stage="delivered",
        status="delivered",
        delivered_date=date.today() - timedelta(days=31),
    )
    refused = await client.post(f"/api/v1/orders/{late}/return", headers=me,
                                json={"reason": "Changed my mind after a month."})  # fmt: skip
    assert refused.status_code == 409


async def test_other_customers_cannot_see_or_touch_an_order(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    ref = (await place_order(client, shopper(create_user, make_token)))["order_ref"]
    stranger = shopper(create_user, make_token, email="stranger@example.test")
    for method, path in [("post", "cancel"), ("get", "events"), ("get", "receipt.pdf")]:
        response = await getattr(client, method)(f"/api/v1/orders/{ref}/{path}", headers=stranger)
        assert response.status_code == 404


async def test_history_and_receipt(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str],
    auth_headers: Callable[[Role], dict[str, str]],
) -> None:  # fmt: skip
    me = shopper(create_user, make_token)
    order = await place_order(client, me)
    events = (await client.get(f"/api/v1/orders/{order['order_ref']}/events", headers=me)).json()
    assert [e["stage"] for e in events] == ["placed"]
    pdf = await client.get(f"/api/v1/orders/{order['order_ref']}/receipt.pdf", headers=me)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["content-type"] == "application/pdf"
    staff = await client.get(f"/api/v1/orders/{order['order_ref']}/receipt.pdf",
                             headers=auth_headers(Role.AGENT))  # fmt: skip
    assert staff.status_code == 200


async def test_the_receipt_shows_the_paid_amount_in_rupees(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    import pymupdf

    from database.models import FxRate

    with sync_session() as db:
        db.add(FxRate(currency="PKR", rate=Decimal("281.4"), fetched_at=datetime.now(UTC)))
    me = shopper(create_user, make_token)
    ref = (await place_order(client, me, currency="PKR"))["order_ref"]
    pdf = (await client.get(f"/api/v1/orders/{ref}/receipt.pdf", headers=me)).content
    with pymupdf.open(stream=pdf, filetype="pdf") as document:  # type: ignore[no-untyped-call]
        text = "".join(page.get_text() for page in document)
    assert ref in text and "Rs 78,511" in text and "USD 279.00" in text
