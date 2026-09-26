"""Load the labelled dataset into the database through the normal intake path.

Customers and orders are upserted; complaints go through `submit_complaint`, so validation,
duplicate detection and risk signals run exactly as for portal submissions. Complaints are
stored with `source="dataset"` and their dataset ID in `external_ref`. They are not analysed
here; run the analysis CLI afterwards.

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


async def load(folder: Path = HERE) -> Counter[str]:
    outcomes: Counter[str] = Counter()
    async with async_session_factory()() as db:
        customers: dict[str, Customer] = {
            c.customer_ref: c for c in (await db.scalars(select(Customer))).all()
        }
        with (folder / "customers.csv").open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["customer_ref"] not in customers:
                    customer = Customer(
                        customer_ref=row["customer_ref"],
                        full_name=row["full_name"],
                        email=row["email"],
                        customer_type=CustomerType(row["customer_type"]),
                    )
                    db.add(customer)
                    customers[row["customer_ref"]] = customer
        await db.flush()

        existing_orders = set((await db.scalars(select(Order.order_ref))).all())
        with (folder / "orders.csv").open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
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
            await db.scalars(select(Complaint.external_ref).where(Complaint.source == "dataset"))
        )
        records: list[dict[str, Any]] = [
            json.loads(line) for line in (folder / "complaints.jsonl").open(encoding="utf-8")
        ]
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
                        order_ref=record["order_ref"],
                        previous_complaint_ref=previous,
                        channel=record["channel"],
                        requested_resolution=record["requested_resolution"],
                    ),
                    submitted_by=None,
                    source="dataset",
                    enqueue=False,
                    created_at=datetime.fromisoformat(record["created_at"]).astimezone(),
                    external_ref=record["dataset_id"],
                )
                refs[record["dataset_id"]] = complaint.complaint_ref
                outcomes["accepted"] += 1
            except DuplicateComplaintError:
                await db.rollback()
                expected = record["expected"]["expected_intake"] == "rejected_duplicate"
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
