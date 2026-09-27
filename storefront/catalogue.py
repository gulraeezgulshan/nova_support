"""Load the demo catalogue from `config/catalogue.yaml` and add products that are missing.

Once a product exists, administrators own it (Products screen); re-seeding never overwrites
their edits.
"""

from decimal import Decimal
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Product
from src.core.config import ROOT_DIR

CATALOGUE_FILE = ROOT_DIR / "config" / "catalogue.yaml"
FIELDS = ("name", "product_line", "description", "specs")
# The order product-category codes the complaint rules and policies know.
PRODUCT_LINES = ("SMARTPHONE", "LAPTOP", "TABLET", "AUDIO", "WEARABLE", "NETWORKING",
                 "SMART_HOME", "ACCESSORY")  # fmt: skip


def load_catalogue() -> list[dict[str, Any]]:
    with CATALOGUE_FILE.open(encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle)
    products: list[dict[str, Any]] = data["products"]
    return products


def sync_catalogue(db: Session) -> dict[str, int]:
    existing = set(db.scalars(select(Product.sku)))
    counts = {"created": 0, "updated": 0}  # "updated" kept for the seed report; always 0
    for item in load_catalogue():
        if item["sku"] in existing:
            continue
        price = Decimal(str(item["price"])).quantize(Decimal("0.01"))
        db.add(
            Product(sku=item["sku"], price=price, is_active=True, **{f: item[f] for f in FIELDS})
        )
        counts["created"] += 1
    db.commit()
    return counts
