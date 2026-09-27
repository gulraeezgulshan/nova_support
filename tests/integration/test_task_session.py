"""Background tasks can use the async intake from several asyncio.run calls in a row."""

import asyncio

import pytest
from sqlalchemy import text

from database.session import task_session

pytestmark = pytest.mark.db


async def _ping() -> int:
    async with task_session() as db:
        return int((await db.execute(text("select 1"))).scalar_one())


def test_task_session_survives_new_event_loops(clean_db: None) -> None:
    assert [asyncio.run(_ping()) for _ in range(3)] == [1, 1, 1]
