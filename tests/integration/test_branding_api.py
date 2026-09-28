"""Logos (content-checked, public) and branding (public, from Settings)."""

from collections.abc import Callable

import httpx
import pytest

from database.models import Role

pytestmark = pytest.mark.db
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


async def test_admin_uploads_a_logo_that_everyone_can_load(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    up = await client.post(
        "/api/v1/settings/logo/shop", headers=admin, files={"file": ("logo.png", PNG, "image/png")}
    )
    assert up.status_code == 200, up.text
    branding = (await client.get("/api/v1/branding")).json()  # no sign-in
    assert branding["shop_logo_url"].startswith("/api/v1/branding/logo/shop?v=")
    image = await client.get("/api/v1/branding/logo/shop")
    assert image.status_code == 200 and image.content == PNG
    assert image.headers["x-content-type-options"] == "nosniff"
    assert (await client.delete("/api/v1/settings/logo/shop", headers=admin)).status_code == 204
    assert (await client.get("/api/v1/branding/logo/shop")).status_code == 404


@pytest.mark.parametrize(
    ("name", "data"),
    [("logo.svg", SVG), ("logo.png", SVG), ("big.png", PNG + b"\x00" * 1024 * 1024)],
    ids=["svg", "svg-renamed-png", "over-1mb"],
)
async def test_unsafe_or_large_logos_are_refused(
    client: httpx.AsyncClient,
    auth_headers: Callable[[Role], dict[str, str]],
    name: str,
    data: bytes,
) -> None:
    response = await client.post(
        "/api/v1/settings/logo/console",
        headers=auth_headers(Role.ADMIN),
        files={"file": (name, data, "image/png")},
    )
    assert response.status_code == 422


async def test_only_admins_upload(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    response = await client.post(
        "/api/v1/settings/logo/shop",
        headers=auth_headers(Role.AGENT),
        files={"file": ("l.png", PNG, "image/png")},
    )
    assert response.status_code == 403


async def test_shop_details_follow_the_settings(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    admin = auth_headers(Role.ADMIN)
    current = (await client.get("/api/v1/settings", headers=admin)).json()
    s = current["settings"]
    branding = {k: v for k, v in s["branding"].items() if not k.endswith("_logo_key")}
    payload = {
        "version": current["version"],
        "email": s["email"],
        "ai": s["ai"],
        "operations": s["operations"],
        "branding": {**branding, "shop_name": "Nova Electronics", "phone": "+92 300 0000000"},
    }
    assert (await client.put("/api/v1/settings", headers=admin, json=payload)).status_code == 200
    company = (await client.get("/api/v1/storefront/config")).json()["company"]
    assert (company["name"], company["phone"]) == ("Nova Electronics", "+92 300 0000000")
    assert (await client.get("/api/v1/branding")).json()["shop_name"] == "Nova Electronics"
