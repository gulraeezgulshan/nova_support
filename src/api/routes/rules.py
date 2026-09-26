"""Complaint Resolution Rule Matrix administration.

Staff can read the matrix; administrators can add or change rules at runtime (the
live-modification challenge). Every change is validated exactly like the CSV import,
versioned and audited.
"""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from complaint_rules.facts import FACTS
from complaint_rules.matrix import (
    EXPORT_COLUMNS,
    RuleMatrixError,
    RuleRecord,
    apply_record,
    export_rows,
)
from database import audit
from database.models import Category, Department, Role, Rule, User
from database.session import get_db
from security.dependencies import STAFF_ROLES, require_roles
from src.api.schemas import ErrorResponse, FactOut, RuleOut, RuleWrite

router = APIRouter(prefix="/rules", tags=["rules"])
staff = require_roles(*STAFF_ROLES)
admin_only = require_roles(Role.ADMIN)


async def _validated(db: AsyncSession, payload: RuleWrite) -> RuleRecord:
    try:
        record = RuleRecord.model_validate(payload.model_dump())
        departments = set((await db.scalars(select(Department.code))).all())
        categories = {
            c.code: {s.code for s in c.subcategories}
            for c in (await db.scalars(select(Category))).all()
        }
        record.check_references(departments, categories)
    except RuleMatrixError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "; ".join(exc.errors)) from exc
    except ValueError as exc:  # pydantic ValidationError is a ValueError
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return record


@router.get("", response_model=list[RuleOut])
async def list_rules(_: User = Depends(staff), db: AsyncSession = Depends(get_db)) -> list[Rule]:
    return list((await db.scalars(select(Rule).order_by(Rule.rule_type, Rule.rule_id))).all())


@router.get("/facts", response_model=list[FactOut])
async def list_facts(_: User = Depends(staff)) -> list[FactOut]:
    return [FactOut(name=name, type=f.type, description=f.description) for name, f in FACTS.items()]


@router.get("/export.csv", response_class=Response)
async def export_rules(_: User = Depends(staff), db: AsyncSession = Depends(get_db)) -> Response:
    rules = (await db.scalars(select(Rule).order_by(Rule.rule_type, Rule.rule_id))).all()
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerows(export_rows(rules))
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="rule_matrix.csv"'},
    )


@router.post(
    "",
    response_model=RuleOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def create_rule(
    payload: RuleWrite, actor: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> Rule:
    record = await _validated(db, payload)
    if await db.scalar(select(Rule.id).where(Rule.rule_id == record.rule_id)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Rule {record.rule_id} already exists")
    rule = Rule(version=1)
    apply_record(rule, record)
    db.add(rule)
    await db.flush()
    await audit.record(
        db,
        "rule.created",
        "rule",
        record.rule_id,
        actor_user_id=actor.id,
        after=record.model_dump(mode="json"),
    )
    await db.commit()
    return rule


@router.put("/{rule_id}", response_model=RuleOut, responses={422: {"model": ErrorResponse}})
async def replace_rule(
    rule_id: str,
    payload: RuleWrite,
    actor: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
) -> Rule:
    rule = await db.scalar(select(Rule).where(Rule.rule_id == rule_id))
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    if payload.rule_id != rule_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "rule_id cannot be changed")
    record = await _validated(db, payload)
    before = RuleOut.model_validate(rule).model_dump(mode="json")
    if apply_record(rule, record):
        rule.version += 1
        await audit.record(
            db,
            "rule.updated",
            "rule",
            rule_id,
            actor_user_id=actor.id,
            before=before,
            after=record.model_dump(mode="json"),
        )
        await db.commit()
    return rule
