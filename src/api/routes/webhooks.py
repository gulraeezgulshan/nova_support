"""Clerk user-sync webhook (delivered and signed by Svix)."""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from database import audit
from database.models import User
from database.session import get_db
from security.provisioning import upsert_user
from src.core.config import Settings, get_settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"], include_in_schema=False)


def _primary_email(data: dict[str, Any]) -> str | None:
    primary_id = data.get("primary_email_address_id")
    for entry in data.get("email_addresses") or []:
        if entry.get("id") == primary_id:
            return str(entry.get("email_address")) or None
    return None


def _full_name(data: dict[str, Any]) -> str | None:
    name = " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p)
    return name or None


@router.post("/clerk", status_code=status.HTTP_204_NO_CONTENT)
async def clerk_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    if not settings.clerk_webhook_signing_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Webhook secret not configured")
    body = await request.body()
    try:
        # svix >= 2 only validates the signature; the payload is parsed separately.
        Webhook(settings.clerk_webhook_signing_secret).verify(body, dict(request.headers))
    except WebhookVerificationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature") from exc
    event: dict[str, Any] = json.loads(body)

    event_type = event.get("type")
    data: dict[str, Any] = event.get("data") or {}
    clerk_user_id = data.get("id")
    if not clerk_user_id:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if event_type in ("user.created", "user.updated"):
        await upsert_user(db, clerk_user_id, _primary_email(data), _full_name(data))
    elif event_type == "user.deleted":
        user = await db.scalar(select(User).where(User.clerk_user_id == clerk_user_id))
        if user is not None and user.is_active:
            user.is_active = False
            await audit.record(db, "user.deactivated", "user", user.id, after={"source": "clerk"})
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
