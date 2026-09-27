"""Seed the configurable taxonomy (`config/taxonomy.yaml`) and the Complaint Resolution
Rule Matrix (`complaint_rules/`, `escalation_rules/`).

Idempotent: existing rows (matched by code / rule_id) are updated, new ones inserted,
nothing deleted. Run with: `uv run python -m database.seed`
"""

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Category, Department, SlaPolicy, Subcategory
from database.session import sync_session
from src.core.config import ROOT_DIR

TAXONOMY_FILE = ROOT_DIR / "config" / "taxonomy.yaml"


def load_taxonomy(path: Path = TAXONOMY_FILE) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle)
    return data


def seed_taxonomy(db: Session, data: dict[str, Any]) -> dict[str, int]:
    counts = {"departments": 0, "categories": 0, "subcategories": 0, "sla_policies": 0}

    for item in data.get("departments", []):
        department = db.scalar(select(Department).where(Department.code == item["code"]))
        if department is None:
            department = Department(code=item["code"])
            db.add(department)
        department.name = item["name"]
        department.description = item.get("description")
        counts["departments"] += 1

    for item in data.get("categories", []):
        category = db.scalar(select(Category).where(Category.code == item["code"]))
        if category is None:
            category = Category(code=item["code"])
            db.add(category)
        category.name = item["name"]
        category.description = item.get("description")
        db.flush()
        counts["categories"] += 1
        for sub in item.get("subcategories", []):
            subcategory = db.scalar(
                select(Subcategory).where(
                    Subcategory.category_id == category.id, Subcategory.code == sub["code"]
                )
            )
            if subcategory is None:
                subcategory = Subcategory(category_id=category.id, code=sub["code"])
                db.add(subcategory)
            subcategory.name = sub["name"]
            subcategory.description = sub.get("description")
            counts["subcategories"] += 1

    for item in data.get("sla_policies", []):
        sla = db.scalar(select(SlaPolicy).where(SlaPolicy.priority == item["priority"]))
        if sla is None:
            sla = SlaPolicy(priority=item["priority"])
            db.add(sla)
        sla.name = item["name"]
        sla.first_response_minutes = item["first_response_minutes"]
        sla.resolution_minutes = item["resolution_minutes"]
        sla.at_risk_threshold_pct = item.get("at_risk_threshold_pct", 75)
        counts["sla_policies"] += 1

    db.flush()
    return counts


def seed_rules(db: Session) -> dict[str, int]:
    from complaint_rules.matrix import RuleMatrixError, read_default_matrix, sync_rules

    departments = set(db.scalars(select(Department.code)).all())
    categories: dict[str, set[str]] = {}
    for category in db.scalars(select(Category)).all():
        categories[category.code] = {s.code for s in category.subcategories}
    records = read_default_matrix()
    errors: list[str] = []
    for record in records:
        try:
            record.check_references(departments, categories)
        except RuleMatrixError as exc:
            errors += exc.errors
    if errors:
        raise RuleMatrixError(errors)
    return sync_rules(db, records)


def main() -> None:
    from storefront.catalogue import sync_catalogue

    with sync_session() as db:
        counts = seed_taxonomy(db, load_taxonomy())
        rule_counts = seed_rules(db)
        product_counts = sync_catalogue(db)
    print("Seeded:", ", ".join(f"{k}={v}" for k, v in counts.items()))
    print("Rules:", ", ".join(f"{k}={v}" for k, v in rule_counts.items()))
    print("Products:", ", ".join(f"{k}={v}" for k, v in product_counts.items()))


if __name__ == "__main__":
    main()
