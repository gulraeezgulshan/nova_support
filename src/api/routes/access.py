"""Page access (admin only): which staff roles may view or edit each console page."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import app_settings
from app_settings import StaleSettingsError
from app_settings.access import PAGES, PageAccess, validate_update
from database.models import Role, User
from database.session import get_db
from security.dependencies import require_roles
from src.api.schemas import AccessOut, AccessPageOut, AccessUpdate

router = APIRouter(tags=["access"])
admin_only = require_roles(Role.ADMIN)


async def _out(db: AsyncSession) -> AccessOut:
    row = await app_settings.current_row(db)
    who = await db.get(User, row.updated_by_id) if row and row.updated_by_id else None
    return AccessOut(
        pages=[
            AccessPageOut(
                key=p.key,
                label=p.label,
                description=p.description,
                has_edit=p.has_edit,
                default=PageAccess(**p.default),
            )
            for p in PAGES
        ],
        matrix=app_settings.load(row.data if row else None).access,
        version=row.version if row else 0,
        updated_at=row.updated_at if row else None,
        updated_by=(who.full_name or who.email) if who else None,
    )


@router.get("/access", response_model=AccessOut)
async def read_access(
    _: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> AccessOut:
    return await _out(db)


@router.put("/access", response_model=AccessOut)
async def update_access(
    payload: AccessUpdate, actor: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> AccessOut:
    try:
        matrix = validate_update(payload.matrix)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    row = await app_settings.current_row(db)
    new = app_settings.load(row.data if row else None).model_copy(update={"access": matrix})
    try:
        await app_settings.save(
            db,
            new,
            actor=actor,
            expected_version=payload.version,
            action="access.updated",
            audit_group="access",
        )
    except StaleSettingsError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Someone else changed the settings; reload and try again."
        ) from exc
    return await _out(db)
