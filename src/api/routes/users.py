import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import audit
from database.models import Department, Role, User
from database.session import get_db
from security.dependencies import get_current_user, require_roles
from src.api.schemas import UserOut, UserUpdate

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserOut)
async def read_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/users", response_model=list[UserOut])
async def list_users(
    _: User = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
) -> list[User]:
    return list((await db.scalars(select(User).order_by(User.created_at))).all())


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    admin: User = Depends(require_roles(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id and (
        payload.role not in (None, Role.ADMIN) or payload.is_active is False
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "Administrators cannot demote themselves")

    changes = payload.model_dump(exclude_unset=True)
    if changes.get("department_id") and await db.get(Department, changes["department_id"]) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown department")

    before = {key: str(getattr(user, key)) for key in changes}
    for key, value in changes.items():
        setattr(user, key, value)
    await audit.record(
        db,
        "user.updated",
        "user",
        user.id,
        actor_user_id=admin.id,
        before=before,
        after={key: str(value) for key, value in changes.items()},
    )
    await db.commit()
    await db.refresh(user, ["department"])
    return user
