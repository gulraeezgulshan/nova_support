"""Create or update local user records from Clerk identities."""

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import audit
from database.models import Role, User
from src.core.config import get_settings


def initial_role_for(email: str | None) -> Role:
    """New users are customers, except e-mails listed in BOOTSTRAP_ADMIN_EMAILS."""
    if email and email.lower() in get_settings().bootstrap_admin_email_set:
        return Role.ADMIN
    return Role.CUSTOMER


async def upsert_user(
    db: AsyncSession,
    clerk_user_id: str,
    email: str | None,
    full_name: str | None,
) -> User:
    """Create the user on first sight; refresh profile fields later. Never changes the role."""
    user = await db.scalar(select(User).where(User.clerk_user_id == clerk_user_id))
    if user is None:
        # ON CONFLICT DO NOTHING makes two simultaneous first requests safe.
        created_id = await db.scalar(
            insert(User)
            .values(
                id=uuid.uuid4(),
                clerk_user_id=clerk_user_id,
                email=email,
                full_name=full_name,
                role=initial_role_for(email),
            )
            .on_conflict_do_nothing(index_elements=[User.clerk_user_id])
            .returning(User.id)
        )
        user = await db.scalar(select(User).where(User.clerk_user_id == clerk_user_id))
        assert user is not None
        if created_id is None:  # another request created it first
            return user
        await audit.record(
            db,
            "user.provisioned",
            "user",
            user.id,
            actor_user_id=user.id,
            after={"email": email, "role": user.role},
        )
        return user

    if email and user.email != email:
        user.email = email
    if full_name and user.full_name != full_name:
        user.full_name = full_name
    return user
