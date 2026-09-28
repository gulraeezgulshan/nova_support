"""Shop and console logos: content-checked images in storage, key saved in Settings."""

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from app_settings.model import LogoTarget
from app_settings.store import current_row, load, save
from database.models import User
from src.core.storage import Storage
from storefront.images import EXTENSIONS, image_type

MAX_LOGO_BYTES = 1024 * 1024


class LogoError(ValueError):
    pass


def check(data: bytes) -> str:
    if not data:
        raise LogoError("The file is empty.")
    if len(data) > MAX_LOGO_BYTES:
        raise LogoError("Logos must be 1 MB or smaller.")
    media_type = image_type(data)  # from the content, never the name: SVG is refused
    if media_type is None:
        raise LogoError("Only PNG, JPEG and WebP logos are accepted.")
    return media_type


async def set_logo(
    db: AsyncSession, target: LogoTarget, data: bytes, storage: Storage, actor: User
) -> str:
    media_type = check(data)
    key = f"branding/{target}-{hashlib.sha256(data).hexdigest()[:12]}.{EXTENSIONS[media_type]}"
    storage.put(key, data, media_type)
    row = await current_row(db)
    settings = load(row.data if row else None)
    settings.branding = settings.branding.model_copy(update={f"{target}_logo_key": key})
    await save(db, settings, actor=actor, expected_version=None)
    return key


async def remove_logo(db: AsyncSession, target: LogoTarget, actor: User) -> None:
    row = await current_row(db)
    settings = load(row.data if row else None)
    settings.branding = settings.branding.model_copy(update={f"{target}_logo_key": None})
    await save(db, settings, actor=actor, expected_version=None)
