"""A signed-in shopper and an order placed through the real checkout."""

from collections.abc import Callable
from typing import Any

import httpx

from database.models import Role, User


def shopper(
    create_user: Callable[..., User],
    make_token: Callable[..., str],
    email: str = "shopper@example.test",
) -> dict[str, str]:
    user = create_user(Role.CUSTOMER, email=email)
    return {"Authorization": f"Bearer {make_token(user.clerk_user_id)}"}


async def place_order(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    sku: str = "VH-AUD-P700",
    currency: str = "USD",
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/checkout",
        headers=headers,
        json={"lines": [{"sku": sku, "quantity": 1}], "currency": currency},
    )
    assert response.status_code == 201, response.text
    order: dict[str, Any] = response.json()[0]
    return order
