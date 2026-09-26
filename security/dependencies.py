"""FastAPI dependencies for authentication and role-based access control (RBAC).

Every protected endpoint declares the roles it accepts, e.g.
`user: User = Depends(require_roles(Role.ADMIN))`. Roles come from our database,
never from the token, so a user cannot grant themselves permissions.
"""

from collections.abc import Awaitable, Callable
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Role, User
from database.session import get_db
from security.clerk import ClerkTokenVerifier, TokenVerificationError
from security.provisioning import upsert_user
from src.core.config import get_settings

bearer_scheme = HTTPBearer(auto_error=False, description="Clerk session token")

STAFF_ROLES = (Role.AGENT, Role.REVIEWER, Role.MANAGER, Role.ADMIN)


@lru_cache
def _default_verifier() -> ClerkTokenVerifier:
    return ClerkTokenVerifier.from_settings(get_settings())


def get_token_verifier() -> ClerkTokenVerifier:
    """Overridable in tests via `app.dependency_overrides`."""
    return _default_verifier()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    verifier: ClerkTokenVerifier = Depends(get_token_verifier),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        # JWKS lookup may do network I/O on a cache miss, so keep it off the event loop.
        identity = await run_in_threadpool(verifier.verify, credentials.credentials)
    except TokenVerificationError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, str(exc), headers={"WWW-Authenticate": "Bearer"}
        ) from exc

    user = await upsert_user(db, identity.clerk_user_id, identity.email, identity.full_name)
    await db.commit()
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated")
    return user


def require_roles(*roles: Role) -> Callable[..., Awaitable[User]]:
    allowed = frozenset(roles)

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role for this action")
        return user

    return dependency
