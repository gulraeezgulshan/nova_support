"""Browse, checkout, orders and admin-only delivery outcomes."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from database.models import Role

pytestmark = pytest.mark.db


async def test_catalogue_is_public(client: httpx.AsyncClient) -> None:
    products = (await client.get("/api/v1/products")).json()
    assert len(products) >= 12
    phones = (await client.get("/api/v1/products", params={"product_line": "SMARTPHONE"})).json()
    assert phones and all(p["product_line"] == "SMARTPHONE" for p in phones)
    assert (await client.get("/api/v1/products/VH-PHN-NX5")).json()["price"] == 749.0
    assert (await client.get("/api/v1/products/NOPE")).status_code == 404


async def test_shop_config_is_public(client: httpx.AsyncClient) -> None:
    config = (await client.get("/api/v1/storefront/config")).json()
    assert config["shipping"]["standard_days"] == 5
    assert config["company"]["name"] == "VoltHaven Electronics"
    assert config["faq"] and "{" not in config["faq"][0]["answer"]


async def test_checkout_prices_on_the_server_and_lists_orders(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    headers = auth_headers(Role.CUSTOMER)
    body = {
        "lines": [{"sku": "VH-PHN-NX5", "quantity": 1}, {"sku": "VH-ACC-VC65", "quantity": 2}],
        "shipping_method": "express",
    }
    response = await client.post("/api/v1/checkout", json=body, headers=headers)
    assert response.status_code == 201, response.text
    orders = response.json()
    assert [o["amount"] for o in orders] == [749.0, 78.0]
    assert len({o["checkout_ref"] for o in orders}) == 1
    assert all(o["order_ref"].startswith("ORD-8") and o["status"] == "processing" for o in orders)
    listed = (await client.get("/api/v1/orders", headers=headers)).json()
    assert {o["order_ref"] for o in listed} == {o["order_ref"] for o in orders}


@pytest.mark.parametrize(
    "body",
    [
        {"lines": [{"sku": "NOPE", "quantity": 1}]},
        {"lines": [{"sku": "VH-PHN-NX5", "quantity": 9}]},
        {"lines": []},
    ],
)
async def test_invalid_checkouts_are_rejected(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]], body: dict[str, Any]
) -> None:
    response = await client.post("/api/v1/checkout", json=body, headers=auth_headers(Role.CUSTOMER))
    assert response.status_code == 422


async def test_checkout_needs_sign_in(client: httpx.AsyncClient) -> None:
    body = {"lines": [{"sku": "VH-PHN-NX5", "quantity": 1}]}
    assert (await client.post("/api/v1/checkout", json=body)).status_code == 401


async def test_delivery_outcomes_are_admin_only(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    [order] = (
        await client.post(
            "/api/v1/checkout",
            headers=admin,
            json={"lines": [{"sku": "VH-LAP-AB14", "quantity": 1}]},
        )
    ).json()
    path = f"/api/v1/orders/{order['order_ref']}/simulate"
    customer = auth_headers(Role.CUSTOMER)
    assert (await client.post(path, json={"outcome": "late"}, headers=customer)).status_code == 403
    late = (await client.post(path, json={"outcome": "late", "days": 5}, headers=admin)).json()
    assert (
        late["status"] == "delivered" and late["delivered_date"] > late["committed_delivery_date"]
    )
