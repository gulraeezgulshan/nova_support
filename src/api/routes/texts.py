"""Settings → Customer texts (admin only): order e-mails, complaint e-mails, chat lines."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import app_settings
from app_settings import StaleSettingsError
from app_settings.texts import PLACEHOLDERS, SAMPLES
from database.models import Role, User
from database.session import get_db
from security.dependencies import require_roles
from src.api.schemas import PlaceholderRule, TextsOut, TextsUpdate

router = APIRouter(tags=["texts"])
admin_only = require_roles(Role.ADMIN)
URL = "/settings/texts"


async def _out(db: AsyncSession) -> TextsOut:
    row = await app_settings.current_row(db)
    who = await db.get(User, row.updated_by_id) if row and row.updated_by_id else None
    current = app_settings.load(row.data if row else None)
    return TextsOut(
        texts=current.texts,
        defaults=app_settings.defaults().texts,
        version=row.version if row else 0,
        updated_at=row.updated_at if row else None,
        updated_by=(who.full_name or who.email) if who else None,
        placeholders={
            path: PlaceholderRule(allowed=list(allowed), required=list(required))
            for path, (allowed, required) in PLACEHOLDERS.items()
        },
        samples={**SAMPLES, "shop": current.branding.shop_name},
    )


@router.get(URL, response_model=TextsOut)
async def read_texts(_: User = Depends(admin_only), db: AsyncSession = Depends(get_db)) -> TextsOut:
    return await _out(db)


@router.put(URL, response_model=TextsOut)
async def update_texts(
    payload: TextsUpdate, actor: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> TextsOut:
    row = await app_settings.current_row(db)
    stored = app_settings.load(row.data if row else None)
    try:
        await app_settings.save(
            db,
            stored.model_copy(update={"texts": payload.texts}),
            actor=actor,
            expected_version=payload.version,
            action="settings.updated",
            audit_group="texts",
        )
    except StaleSettingsError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Someone else changed the settings; reload and try again."
        ) from exc
    return await _out(db)
