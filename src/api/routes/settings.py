"""Run-time settings (admin) and public branding."""

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app_settings
from app_settings import SUGGESTED_MODELS, RuntimeSettings, StaleSettingsError, logos
from app_settings.facts import policy_facts
from app_settings.model import (
    BrandingSettings,
    KnowledgeBaseSettings,
    LogoTarget,
    ValidationSettings,
    known_signals,
)
from database.models import Category, Document, Role, Subcategory, User
from database.session import get_db
from security.dependencies import require_roles
from src.api.schemas import BrandingOut, SettingsGroups, SettingsOut, SettingsUpdate
from src.core.config import get_settings
from src.core.storage import Storage, get_storage
from storefront.images import image_type

router = APIRouter(tags=["settings"])
admin_only = require_roles(Role.ADMIN)


def logo_url(target: str, key: str | None) -> str | None:
    """Relative to the API host; the key in the query string busts caches after a change."""
    return f"/api/v1/branding/logo/{target}?v={key.rsplit('-', 1)[-1]}" if key else None


async def _out(db: AsyncSession) -> SettingsOut:
    row = await app_settings.current_row(db)
    current = app_settings.load(row.data if row else None)
    who = await db.get(User, row.updated_by_id) if row and row.updated_by_id else None
    env = get_settings()
    return SettingsOut(
        settings=SettingsGroups.of(current),
        defaults=SettingsGroups.of(app_settings.defaults()),
        risk_signals=sorted(known_signals()),
        version=row.version if row else 0,
        updated_at=row.updated_at if row else None,
        updated_by=(who.full_name or who.email) if who else None,
        providers_available=[p for p in ("openai", "anthropic") if env.api_key_for(p)],
        suggested_models=SUGGESTED_MODELS,
        policy_facts=await policy_facts(db),
        shop_logo_url=logo_url("shop", current.branding.shop_logo_key),
        console_logo_url=logo_url("console", current.branding.console_logo_key),
    )


async def _check_types_in_use(
    db: AsyncSession, before: KnowledgeBaseSettings, after: KnowledgeBaseSettings
) -> None:
    """A document type may only be removed when no document uses it."""
    removed = {t.code for t in before.document_types} - {t.code for t in after.document_types}
    if not removed:
        return
    rows = (
        await db.execute(
            select(Document.doc_type, Document.doc_code).where(Document.doc_type.in_(removed))
        )
    ).all()
    used: dict[str, list[str]] = {}
    for doc_type, doc_code in rows:
        used.setdefault(doc_type, []).append(doc_code)
    if used:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            " ".join(
                f"{code} is used by {len(docs)} documents ({', '.join(sorted(docs))}); "
                "retire or re-type them first."
                for code, docs in sorted(used.items())
            ),
        )


async def _check_validation_codes(db: AsyncSession, v: ValidationSettings) -> None:
    """Categories and subcategories in the validation settings must exist in the taxonomy."""
    rows = (
        await db.execute(
            select(Category.code, Subcategory.code).outerjoin(
                Subcategory, Subcategory.category_id == Category.id
            )
        )
    ).all()
    subs: dict[str, set[str]] = {}
    for category, subcategory in rows:
        subs.setdefault(category, set())
        if subcategory:
            subs[category].add(subcategory)
    problems = [
        f"Needs an order: category {code} does not exist."
        for code in v.orders_required_for
        if code not in subs
    ]
    for signal, boost in v.signal_boosts.items():
        if boost.category not in subs:
            problems.append(f"Signal boost {signal}: category {boost.category} does not exist.")
        elif boost.subcategory not in subs[boost.category]:
            problems.append(
                f"Signal boost {signal}: subcategory {boost.subcategory} "
                f"is not in category {boost.category}."
            )
    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, " ".join(problems))


@router.get("/settings", response_model=SettingsOut)
async def read_settings(
    _: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> SettingsOut:
    return await _out(db)


@router.put("/settings", response_model=SettingsOut)
async def update_settings(
    payload: SettingsUpdate, actor: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> SettingsOut:
    if not get_settings().api_key_for(payload.ai.provider):
        name = "OPENAI_API_KEY" if payload.ai.provider == "openai" else "ANTHROPIC_API_KEY"
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Add {name} on the server first."
        )
    row = await app_settings.current_row(db)
    stored = app_settings.load(row.data if row else None)
    logos = stored.branding  # logos are set by upload only
    new = RuntimeSettings(
        access=stored.access,  # changed only on the Page access screen
        patterns=stored.patterns,  # changed only on the Patterns page
        analytics=stored.analytics,
        intake=stored.intake,
        shop=stored.shop,
        knowledge_base=payload.knowledge_base or stored.knowledge_base,
        validation=payload.validation or stored.validation,
        email=payload.email,
        ai=payload.ai,
        operations=payload.operations,
        orders=payload.orders,
        branding=BrandingSettings(
            **payload.branding.model_dump(),
            shop_logo_key=logos.shop_logo_key,
            console_logo_key=logos.console_logo_key,
        ),
    )
    if payload.knowledge_base is not None:
        await _check_types_in_use(db, stored.knowledge_base, payload.knowledge_base)
    if payload.validation is not None:
        await _check_validation_codes(db, payload.validation)
    try:
        await app_settings.save(db, new, actor=actor, expected_version=payload.version)
    except StaleSettingsError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Someone else changed the settings; reload and try again."
        ) from exc
    return await _out(db)


@router.post("/settings/logo/{target}", response_model=SettingsOut)
async def upload_logo(
    target: LogoTarget,
    file: UploadFile = File(...),
    actor: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> SettingsOut:
    try:
        await logos.set_logo(db, target, await file.read(), storage, actor)
    except logos.LogoError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return await _out(db)


@router.delete("/settings/logo/{target}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_logo(
    target: LogoTarget, actor: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> Response:
    await logos.remove_logo(db, target, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/branding", response_model=BrandingOut)
async def read_branding() -> BrandingOut:
    b = app_settings.runtime().branding
    return BrandingOut(
        **b.model_dump(exclude={"shop_logo_key", "console_logo_key"}),
        shop_logo_url=logo_url("shop", b.shop_logo_key),
        console_logo_url=logo_url("console", b.console_logo_key),
    )


@router.get(
    "/branding/logo/{target}",
    response_class=Response,
    responses={200: {"content": {"image/*": {}}}},
)
async def branding_logo(target: LogoTarget, storage: Storage = Depends(get_storage)) -> Response:
    key = getattr(app_settings.runtime().branding, f"{target}_logo_key")
    if key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No logo")
    data = await run_in_threadpool(storage.get, key)
    return Response(
        content=data,
        media_type=image_type(data) or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"},
    )
