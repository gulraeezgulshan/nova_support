"""require_access / ensure_access: 403 with a clear message, administrators always pass."""

import uuid

import httpx
import pytest
from fastapi import Depends, FastAPI, HTTPException

from database.models import Role, User
from security.dependencies import NO_ACCESS, ensure_access, get_current_user, require_access


def app_as(role: Role) -> FastAPI:
    app = FastAPI()

    @app.get("/rules-edit")
    async def rules_edit(_: User = Depends(require_access("rules", "edit"))) -> dict[str, str]:
        return {"ok": "yes"}

    app.dependency_overrides[get_current_user] = lambda: User(
        id=uuid.uuid4(), clerk_user_id="u", role=role
    )
    return app


async def get(app: FastAPI) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as http:
        return await http.get("/rules-edit")


async def test_role_without_the_level_gets_403_with_the_message() -> None:
    r = await get(app_as(Role.MANAGER))
    assert r.status_code == 403 and r.json()["detail"] == NO_ACCESS == (
        "You don't have access to this page"
    )


async def test_admin_passes() -> None:
    assert (await get(app_as(Role.ADMIN))).status_code == 200


def test_ensure_access_raises_for_a_staff_branch() -> None:
    agent = User(id=uuid.uuid4(), clerk_user_id="a", role=Role.AGENT)
    with pytest.raises(HTTPException) as exc:
        ensure_access(agent, "imports", "view")
    assert exc.value.status_code == 403
    ensure_access(agent, "complaints", "edit")  # allowed by default: no exception
