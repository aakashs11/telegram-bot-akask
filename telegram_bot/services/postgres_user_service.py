"""Student profiles stored in the students table.

The public methods match UserService. The Google Sheet is not touched.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from telegram_bot.infrastructure.database import Database
from telegram_bot.infrastructure.postgres_students import students
from telegram_bot.services.user_service import apply_class_promotion

logger = logging.getLogger(__name__)

_WRITABLE = {
    "username",
    "current_class",
    "preferred_subject",
    "class_updated_year",
}


class PostgresUserService:
    """Read and write one students row per Telegram user."""

    def __init__(self, database: Database):
        self.database = database
        self._cache: Dict[int, Dict[str, Any]] = {}

    async def get_user_profile(self, user_id: int, username: str = "") -> Dict[str, Any]:
        """Return the profile, creating a blank one when the student is new."""
        if user_id in self._cache:
            return self._cache[user_id]

        async with self.database.engine.connect() as connection:
            row = (
                await connection.execute(
                    select(students).where(students.c.telegram_user_id == user_id)
                )
            ).mappings().first()

        if row is None:
            now = datetime.now(timezone.utc)
            profile = {
                "user_id": user_id,
                "username": username,
                "current_class": None,
                "preferred_subject": None,
                "created_at": now.isoformat(),
                "last_updated": now.isoformat(),
                "class_updated_year": now.year,
            }
            try:
                async with self.database.engine.begin() as connection:
                    await connection.execute(
                        insert(students).values(
                            telegram_user_id=user_id,
                            username=username,
                            current_class=None,
                            preferred_subject=None,
                            created_at=now,
                            last_updated=now,
                            class_updated_year=now.year,
                        )
                    )
            except IntegrityError:
                logger.exception("Could not create student %s", user_id)
                return {}
            self._cache[user_id] = profile
            return profile

        profile = {
            "user_id": int(row["telegram_user_id"]),
            "username": row["username"] or "",
            "current_class": row["current_class"],
            "preferred_subject": row["preferred_subject"],
            "class_updated_year": int(row["class_updated_year"]),
        }
        promoted = apply_class_promotion(profile, datetime.now())
        if promoted != profile:
            await self.update_user_profile(user_id, promoted)
            profile = promoted
        self._cache[user_id] = profile
        return profile

    async def update_user_profile(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """Update class, subject, or the promotion year. Missing students are not created."""
        values = {key: updates[key] for key in _WRITABLE if key in updates}
        values["last_updated"] = datetime.now(timezone.utc)
        if user_id in self._cache:
            self._cache[user_id].update(updates)
            self._cache[user_id]["last_updated"] = values["last_updated"].isoformat()

        async with self.database.engine.begin() as connection:
            result = await connection.execute(
                students.update()
                .where(students.c.telegram_user_id == user_id)
                .values(**values)
            )
        return result.rowcount == 1
