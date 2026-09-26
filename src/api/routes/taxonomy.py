"""Configurable taxonomy endpoints. Staff can read; administrators can change it at runtime."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import audit
from database.models import Category, Department, Role, SlaPolicy, Subcategory, User
from database.session import get_db
from security.dependencies import STAFF_ROLES, get_current_user, require_roles
from src.api.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    SlaPolicyOut,
    SlaPolicyUpdate,
    SubcategoryCreate,
    SubcategoryOut,
    VocabularyOut,
)
from src.core.domain import actions, analysis_config

router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])
admin_only = require_roles(Role.ADMIN)


async def _flush_or_conflict(db: AsyncSession, what: str) -> None:
    """Insert now so a duplicate code becomes a clean 409 instead of a server error."""
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"{what} code already exists") from exc


async def _apply_update(
    db: AsyncSession, entity: Any, changes: dict[str, Any], actor: User, entity_type: str
) -> None:
    before = {key: getattr(entity, key) for key in changes}
    for key, value in changes.items():
        setattr(entity, key, value)
    await audit.record(
        db,
        f"{entity_type}.updated",
        entity_type,
        entity.id,
        actor_user_id=actor.id,
        before=before,
        after=changes,
    )
    await db.commit()


# --- departments ---------------------------------------------------------------


@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(
    _: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Department]:
    return list((await db.scalars(select(Department).order_by(Department.name))).all())


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate,
    actor: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
) -> Department:
    department = Department(**payload.model_dump())
    db.add(department)
    await _flush_or_conflict(db, "Department")
    await audit.record(
        db,
        "department.created",
        "department",
        department.id,
        actor_user_id=actor.id,
        after=payload.model_dump(),
    )
    await db.commit()
    return department


@router.patch("/departments/{department_id}", response_model=DepartmentOut)
async def update_department(
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    actor: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
) -> Department:
    department = await db.get(Department, department_id)
    if department is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")
    await _apply_update(db, department, payload.model_dump(exclude_unset=True), actor, "department")
    return department


# --- categories ----------------------------------------------------------------


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    _: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Category]:
    return list((await db.scalars(select(Category).order_by(Category.name))).all())


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    actor: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
) -> Category:
    category = Category(**payload.model_dump(), subcategories=[])
    db.add(category)
    await _flush_or_conflict(db, "Category")
    await audit.record(
        db,
        "category.created",
        "category",
        category.id,
        actor_user_id=actor.id,
        after=payload.model_dump(),
    )
    await db.commit()
    return category


@router.patch("/categories/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    actor: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
) -> Category:
    category = await db.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    await _apply_update(db, category, payload.model_dump(exclude_unset=True), actor, "category")
    return category


@router.post(
    "/categories/{category_id}/subcategories",
    response_model=SubcategoryOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_subcategory(
    category_id: uuid.UUID,
    payload: SubcategoryCreate,
    actor: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
) -> Subcategory:
    if await db.get(Category, category_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    subcategory = Subcategory(category_id=category_id, **payload.model_dump())
    db.add(subcategory)
    await _flush_or_conflict(db, "Subcategory")
    await audit.record(
        db,
        "subcategory.created",
        "subcategory",
        subcategory.id,
        actor_user_id=actor.id,
        after={**payload.model_dump(), "category_id": str(category_id)},
    )
    await db.commit()
    return subcategory


# --- SLA -----------------------------------------------------------------------


@router.get("/sla-policies", response_model=list[SlaPolicyOut])
async def list_sla_policies(
    _: User = Depends(require_roles(*STAFF_ROLES)), db: AsyncSession = Depends(get_db)
) -> list[SlaPolicy]:
    return list((await db.scalars(select(SlaPolicy).order_by(SlaPolicy.priority))).all())


@router.patch("/sla-policies/{sla_id}", response_model=SlaPolicyOut)
async def update_sla_policy(
    sla_id: uuid.UUID,
    payload: SlaPolicyUpdate,
    actor: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
) -> SlaPolicy:
    sla = await db.get(SlaPolicy, sla_id)
    if sla is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SLA policy not found")
    await _apply_update(db, sla, payload.model_dump(exclude_unset=True), actor, "sla_policy")
    return sla


# --- controlled vocabulary ---------------------------------------------------------------


@router.get("/vocabulary", response_model=VocabularyOut)
async def get_vocabulary(_: User = Depends(require_roles(*STAFF_ROLES))) -> VocabularyOut:
    """Controlled values from `config/analysis.yaml` and `config/actions.yaml`, for filters
    and the rule editor (so the UI never hard-codes them)."""
    cfg = analysis_config()
    return VocabularyOut.model_validate(
        {
            "sentiments": cfg.sentiments,
            "urgencies": cfg.urgencies,
            "priorities": cfg.priorities,
            "channels": cfg.complaint_channels,
            "follow_up_types": cfg.follow_up_types,
            "escalation_levels": [lv.model_dump() for lv in cfg.escalation_levels],
            "actions": [a.model_dump() for a in actions().values()],
        }
    )
