"""Admin product management: create, edit, hide, images (upload, order, delete, serve)."""

import io
from collections.abc import Callable

import httpx
import pytest
from sqlalchemy import select

from database.models import Product, Role
from database.session import sync_session
from storefront.catalogue import sync_catalogue

pytestmark = pytest.mark.db

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 64
NEW = {
    "sku": "VH-TST-001",
    "name": "Test Gadget 1",
    "product_line": "ACCESSORY",
    "price": 24.5,
    "description": "A gadget for tests.",
    "specs": ["Small", "Useful"],
}


@pytest.fixture
def admin(auth_headers: Callable[[Role], dict[str, str]]) -> dict[str, str]:
    return auth_headers(Role.ADMIN)


async def upload(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    sku: str,
    data: bytes,
    name: str = "photo.png",
) -> httpx.Response:
    return await client.post(
        f"/api/v1/admin/products/{sku}/images",
        headers=headers,
        files={"file": (name, io.BytesIO(data), "application/octet-stream")},
    )


async def test_only_admins_manage_products(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    for role in (Role.CUSTOMER, Role.AGENT, Role.MANAGER):
        headers = auth_headers(role)
        assert (await client.get("/api/v1/admin/products", headers=headers)).status_code == 403
        assert (
            await client.post("/api/v1/admin/products", json=NEW, headers=headers)
        ).status_code == 403


async def test_create_edit_and_hide(client: httpx.AsyncClient, admin: dict[str, str]) -> None:
    created = await client.post("/api/v1/admin/products", json=NEW, headers=admin)
    assert created.status_code == 201, created.text
    assert (await client.post("/api/v1/admin/products", json=NEW, headers=admin)).status_code == 409
    bad = await client.post(
        "/api/v1/admin/products",
        headers=admin,
        json={**NEW, "sku": "VH-TST-002", "product_line": "SPACESHIP"},
    )
    assert bad.status_code == 422
    edited = await client.patch(
        "/api/v1/admin/products/VH-TST-001",
        headers=admin,
        json={"price": 19.99, "name": "Test Gadget One"},
    )
    assert (edited.json()["price"], edited.json()["name"]) == (19.99, "Test Gadget One")
    assert (await client.get("/api/v1/products/VH-TST-001")).status_code == 200
    await client.patch(
        "/api/v1/admin/products/VH-TST-001", json={"is_active": False}, headers=admin
    )
    assert (await client.get("/api/v1/products/VH-TST-001")).status_code == 404
    listed = (await client.get("/api/v1/admin/products", headers=admin)).json()
    assert any(p["sku"] == "VH-TST-001" and not p["is_active"] for p in listed)
    checkout = await client.post(
        "/api/v1/checkout", headers=admin, json={"lines": [{"sku": "VH-TST-001", "quantity": 1}]}
    )
    assert checkout.status_code == 422


async def test_images_upload_order_serve_and_delete(
    client: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    sku = "VH-LAP-AB14"
    first = await upload(client, admin, sku, PNG)
    assert first.status_code == 201, first.text
    second = await upload(client, admin, sku, JPEG, "side.jpg")
    third = await upload(client, admin, sku, WEBP, "back.webp")
    ids = [r.json()["id"] for r in (first, second, third)]

    product = (await client.get(f"/api/v1/products/{sku}")).json()
    assert [i["id"] for i in product["images"]] == ids
    served = await client.get(product["images"][0]["url"])
    assert served.status_code == 200 and served.headers["content-type"] == "image/png"
    assert served.content == PNG

    reordered = await client.put(
        f"/api/v1/admin/products/{sku}/images/order",
        headers=admin,
        json={"image_ids": [ids[2], ids[0], ids[1]]},
    )
    assert [i["id"] for i in reordered.json()["images"]] == [ids[2], ids[0], ids[1]]
    removed = await client.delete(f"/api/v1/admin/products/{sku}/images/{ids[0]}", headers=admin)
    assert [i["id"] for i in removed.json()["images"]] == [ids[2], ids[1]]
    assert (await client.get(f"/api/v1/product-images/{ids[0]}")).status_code == 404


@pytest.mark.parametrize(
    ("data", "name"),
    [
        (b"%PDF-1.7 not an image", "fake.png"),
        (b"", "empty.png"),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024), "huge.png"),
    ],
    ids=["disguised-pdf", "empty", "over-5-mb"],
)
async def test_invalid_images_are_rejected(
    client: httpx.AsyncClient, admin: dict[str, str], data: bytes, name: str
) -> None:
    assert (await upload(client, admin, "VH-LAP-AB14", data, name)).status_code == 422


async def test_at_most_five_images(client: httpx.AsyncClient, admin: dict[str, str]) -> None:
    for _ in range(5):
        assert (await upload(client, admin, "VH-AUD-PBP", PNG)).status_code == 201
    assert (await upload(client, admin, "VH-AUD-PBP", PNG)).status_code == 422


async def test_seed_never_overwrites_admin_edits(
    client: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    await client.patch("/api/v1/admin/products/VH-PHN-NX5", json={"price": 699.0}, headers=admin)
    with sync_session() as db:
        assert sync_catalogue(db) == {"created": 0, "updated": 0}
        product = db.scalar(select(Product).where(Product.sku == "VH-PHN-NX5"))
        assert product is not None and float(product.price) == 699.0


async def test_orders_show_the_main_product_image(
    client: httpx.AsyncClient,
    admin: dict[str, str],
    auth_headers: Callable[[Role], dict[str, str]],
) -> None:
    image = (await upload(client, admin, "VH-SMH-CAM", PNG)).json()
    customer = auth_headers(Role.CUSTOMER)
    await client.post(
        "/api/v1/checkout",
        headers=customer,
        json={
            "lines": [{"sku": "VH-SMH-CAM", "quantity": 1}, {"sku": "VH-ACC-USBC2", "quantity": 1}]
        },
    )
    orders = {
        o["product_name"]: o for o in (await client.get("/api/v1/orders", headers=customer)).json()
    }
    assert orders["HomeHub Cam doorbell"]["image_url"] == image["url"]
    assert orders["VoltLink USB-C cable (2 m)"]["image_url"] is None
