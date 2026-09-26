from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_db
from src.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def liveness() -> dict[str, str]:
    """The process is up (used by the platform to restart a hung container)."""
    return {"status": "ok"}


@router.get("/readyz")
async def readiness(response: Response, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Dependencies are reachable (traffic is only routed to ready instances)."""
    checks: dict[str, str] = {}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
    try:
        redis = Redis.from_url(get_settings().redis_url)
        async with redis:
            await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
    if any(value != "ok" for value in checks.values()):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return checks
