"""The demo catalogue is valid data for the shop and the complaint rules."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from database.models import Product
from database.session import sync_session
from storefront.catalogue import load_catalogue, sync_catalogue

PRODUCT_LINES = {
    "SMARTPHONE",
    "LAPTOP",
    "TABLET",
    "AUDIO",
    "WEARABLE",
    "NETWORKING",
    "SMART_HOME",
    "ACCESSORY",
}  # the order product-category codes


def test_catalogue_is_valid() -> None:
    products = load_catalogue()
    assert len(products) >= 12
    skus = [p["sku"] for p in products]
    assert len(skus) == len(set(skus))
    for p in products:
        assert p["product_line"] in PRODUCT_LINES, p["sku"]
        assert Decimal(str(p["price"])) > 0
        assert p["specs"] and all(isinstance(s, str) for s in p["specs"])
    assert {p["product_line"] for p in products} == PRODUCT_LINES


@pytest.mark.db
def test_sync_is_idempotent(clean_db: None) -> None:  # clean_db already synced once
    with sync_session() as db:
        assert sync_catalogue(db) == {"created": 0, "updated": 0}
        assert db.scalar(select(func.count()).select_from(Product)) == len(load_catalogue())
