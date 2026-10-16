"""Students table constraints after Alembic upgrade."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from telegram_bot.infrastructure.database import async_database_url
from telegram_bot.infrastructure.postgres_students import students

pytestmark = pytest.mark.integration


def _profile(**overrides: object) -> dict[str, object]:
    now = datetime(2026, 10, 3, tzinfo=timezone.utc)
    values: dict[str, object] = {
        "telegram_user_id": 4242,
        "username": "riya",
        "current_class": 10,
        "preferred_subject": "AI",
        "created_at": now,
        "last_updated": now,
        "class_updated_year": 2026,
    }
    values.update(overrides)
    return values


@pytest.mark.asyncio
async def test_students_table_stores_a_profile_and_rejects_invalid_values(
    migrated_postgres_url: str,
) -> None:
    engine = create_async_engine(async_database_url(migrated_postgres_url))
    try:
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE TABLE students"))
            await connection.execute(students.insert().values(**_profile()))
            await connection.execute(
                students.insert().values(
                    **_profile(
                        telegram_user_id=4243,
                        username="",
                        current_class=None,
                        preferred_subject=None,
                    )
                )
            )

        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT telegram_user_id, current_class, preferred_subject "
                        "FROM students ORDER BY telegram_user_id"
                    )
                )
            ).all()
            telegram_id_default = await connection.run_sync(
                lambda sync_connection: next(
                    column["default"]
                    for column in inspect(sync_connection).get_columns("students")
                    if column["name"] == "telegram_user_id"
                )
            )

        assert rows == [(4242, 10, "AI"), (4243, None, None)]
        assert telegram_id_default is None

        for invalid in (
            {"telegram_user_id": 4244, "current_class": 9},
            {"telegram_user_id": 4245, "preferred_subject": "Math"},
        ):
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await connection.execute(
                        students.insert().values(**_profile(**invalid))
                    )
    finally:
        await engine.dispose()
