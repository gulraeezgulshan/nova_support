"""Load the labelled dataset into the database through the normal intake path.

Customers and orders are upserted; complaints go through `submit_complaint`, so validation,
duplicate detection and risk signals run exactly as for portal submissions. Complaints are
stored with `source="dataset"` and their dataset ID in `external_ref`. They are not analysed
here; run the analysis CLI afterwards.

The same loader imports evaluation packs (`hidden_test_ready/<pack>/`) with
`source="evaluation"`; `customers.csv` and `orders.csv` are optional there, and customers
named in the complaints but not in a customers file are created on the fly.

Usage (repo root): `uv run python -m sample_complaints.load_dataset`
"""

import asyncio
import csv
import json
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select

from complaint_processing.service import (
    ComplaintInput,
    ComplaintValidationError,
    DuplicateComplaintError,
    submit_complaint,
)
from database.models import Complaint, Customer, CustomerType, Order
from database.session import async_session_factory
from src.core.logging import configure_logging

HERE = Path(__file__).resolve().parent


def _date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


async def load(folder: Path = HERE, source: str = "dataset") -> Counter[str]:
    outcomes: Counter[str] = Counter()
    records: list[dict[str, Any]] = [
        json.loads(line)
        for line in (folder / "complaints.jsonl").open(encoding="utf-8")
        if line.strip()
    ]
    for record in records:  # evaluation packs may leave these out
        record.setdefault("customer_ref", None)
        record["customer_ref"] = record["customer_ref"] or f"CUST-{record['dataset_id']}"[:20]
        record["created_at"] = record.get("created_at") or datetime.now().isoformat()
    async with async_session_factory()() as db:
        customers: dict[str, Customer] = {
            c.customer_ref: c for c in (await db.scalars(select(Customer))).all()
        }
        customer_rows = _rows(folder / "customers.csv")
        named = {row["customer_ref"] for row in customer_rows}
        customer_rows += [
            {
                "customer_ref": ref,
                "full_name": f"Evaluation customer {ref}",
                "email": "",
                "customer_type": "STANDARD",
            }
            for ref in dict.fromkeys(r["customer_ref"] for r in records)
            if ref not in named
        ]
        for row in customer_rows:
            if row["customer_ref"] not in customers:
                customer = Customer(
                    customer_ref=row["customer_ref"],
                    full_name=row["full_name"],
                    email=row["email"] or None,
                    customer_type=CustomerType(row["customer_type"]),
                )
                db.add(customer)
                customers[row["customer_ref"]] = customer
        await db.flush()

        existing_orders = set((await db.scalars(select(Order.order_ref))).all())
        for row in _rows(folder / "orders.csv"):
            if row["order_ref"] in existing_orders:
                continue
            db.add(
                Order(
                    order_ref=row["order_ref"],
                    transaction_ref=row["transaction_ref"] or None,
                    customer_id=customers[row["customer_ref"]].id,
                    product_name=row["product_name"],
                    product_category=row["product_category"],
                    amount=Decimal(row["amount"]),
                    shipping_method=row["shipping_method"],
                    order_date=_date(row["order_date"]),
                    committed_delivery_date=_date(row["committed_delivery_date"]),
                    delivered_date=_date(row["delivered_date"]),
                    status=row["status"],
                )
            )
        await db.commit()
        # Keep IDs, not ORM objects: a rollback after a rejected complaint expires objects.
        customer_ids = {ref: c.id for ref, c in customers.items()}

        loaded = set(
            await db.scalars(select(Complaint.external_ref).where(Complaint.source == source))
        )
        refs: dict[str, str] = {}
        for record in sorted(records, key=lambda r: r["created_at"]):
            if record["dataset_id"] in loaded:
                outcomes["already loaded"] += 1
                continue
            previous = refs.get(record.get("previous_dataset_id") or "")
            try:
                current = await db.get(Customer, customer_ids[record["customer_ref"]])
                assert current is not None
                complaint = await submit_complaint(
                    db,
                    customer=current,
                    data=ComplaintInput(
                        title=record["title"],
                        description=record["description"],
                        order_ref=record.get("order_ref"),
                        previous_complaint_ref=previous,
                        channel=record.get("channel") or "web_form",
                        requested_resolution=record.get("requested_resolution"),
                    ),
                    submitted_by=None,
                    source=source,
                    enqueue=False,
                    created_at=datetime.fromisoformat(record["created_at"]).astimezone(),
                    external_ref=record["dataset_id"],
                )
                refs[record["dataset_id"]] = complaint.complaint_ref
                outcomes["accepted"] += 1
            except DuplicateComplaintError:
                await db.rollback()
                expected = record.get("expected", {}).get("expected_intake") == "rejected_duplicate"
                outcomes["rejected duplicate (expected)" if expected else "rejected duplicate"] += 1
            except ComplaintValidationError as exc:
                await db.rollback()
                outcomes["rejected invalid"] += 1
                print(f"  {record['dataset_id']}: {exc}")
    return outcomes


if __name__ == "__main__":
    configure_logging("WARNING", json=False)
    for outcome, count in asyncio.run(load()).items():
        print(f"{count:5}  {outcome}")
