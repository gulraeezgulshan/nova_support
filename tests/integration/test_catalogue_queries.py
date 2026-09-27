"""Catalogue search, price range and sorting, including real best sellers."""

from collections.abc import Callable
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import select

from database.models import Order, Role
from database.session import sync_session

pytestmark = pytest.mark.db


async def skus(client: httpx.AsyncClient, **params: str | float) -> list[str]:
    response = await client.get("/api/v1/products", params=params)
    assert response.status_code == 200, response.text
    return [p["sku"] for p in response.json()]


async def test_search_matches_name_description_and_specs(client: httpx.AsyncClient) -> None:
    assert set(await skus(client, q="aerobook")) == {"VH-LAP-AB14", "VH-LAP-AB16P"}  # name
    assert await skus(client, q="noise-cancelling") == ["VH-AUD-PBP"]  # description
    assert "VH-ACC-PB20" in await skus(client, q="20,000 mAh")  # a spec


@pytest.mark.parametrize(
    ("term", "expected"),
    [("%", []), ("_", []), ("'", []), ("\\", []), ("(2 m)", ["VH-ACC-USBC2"])],
)
async def test_search_metacharacters_are_literal(
    client: httpx.AsyncClient, term: str, expected: list[str]
) -> None:
    assert await skus(client, q=term) == expected


async def test_price_range(client: httpx.AsyncClient) -> None:
    assert set(await skus(client, max_price=40)) == {"VH-ACC-VC65", "VH-ACC-USBC2"}
    assert set(await skus(client, min_price=1500)) == {"VH-LAP-AB16P"}
    assert await skus(client, min_price=500, max_price=100) == []


async def test_price_sorting(client: httpx.AsyncClient) -> None:
    for sort, reverse in [("price_asc", False), ("price_desc", True)]:
        response = await client.get("/api/v1/products", params={"sort": sort})
        prices = [p["price"] for p in response.json()]
        assert prices == sorted(prices, reverse=reverse)
    assert (await client.get("/api/v1/products", params={"sort": "cheapest"})).status_code == 422


async def test_best_sellers_count_recent_orders_that_were_not_lost(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    buyer = auth_headers(Role.CUSTOMER)

    async def buy(sku: str, quantity: int = 1) -> None:
        body = {"lines": [{"sku": sku, "quantity": quantity}]}
        assert (await client.post("/api/v1/checkout", headers=buyer, json=body)).status_code == 201

    await buy("VH-AUD-PBP", 2)
    await buy("VH-WEA-ST3")
    for _ in range(3):  # three chargers, but one lost and two too old: they don't count
        await buy("VH-ACC-VC65", 5)
    with sync_session() as db:
        chargers = db.scalars(select(Order).where(Order.product_name.like("VoltCharge%"))).all()
        assert len(chargers) == 3
        chargers[0].status = "lost"
        for old in chargers[1:]:
            old.order_date = date.today() - timedelta(days=120)
        db.commit()
    assert (await skus(client, sort="best_selling"))[:2] == ["VH-AUD-PBP", "VH-WEA-ST3"]


async def test_newest_first(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    new = {"sku": "VH-NEW-001", "name": "Brand New Thing", "product_line": "WEARABLE",
           "price": 9999, "description": "Newest product.", "specs": []}  # fmt: skip
    admin = auth_headers(Role.ADMIN)
    assert (await client.post("/api/v1/admin/products", headers=admin, json=new)).status_code == 201
    assert (await skus(client, sort="newest"))[0] == "VH-NEW-001"


async def test_hidden_products_are_never_listed(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    await client.patch(
        "/api/v1/admin/products/VH-AUD-PBP", headers=admin, json={"is_active": False}
    )
    for sort in ["featured", "best_selling", "newest"]:
        assert "VH-AUD-PBP" not in await skus(client, sort=sort, q="earbuds")
