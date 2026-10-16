"""Moderation strikes stored in the warnings table.

The public methods match WarningService. The Google Sheet is not touched.
A second warning in the same chat is a ban, the same rule as the sheet.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from telegram_bot.infrastructure.database import Database
from telegram_bot.infrastructure.postgres_warnings import warnings
from telegram_bot.services.moderation.warning_service import WarningResult

logger = logging.getLogger(__name__)

BAN_THRESHOLD = 2


def warning_crosses_ban(current_count: int) -> tuple[int, bool]:
    """Return the next count and whether that count bans the user."""
    new_count = current_count + 1
    return new_count, new_count >= BAN_THRESHOLD


class PostgresWarningService:
    """Read and write one warnings row per user in a chat."""

    def __init__(self, database: Database):
        self.database = database
        self._cache: dict[str, dict[str, int | bool]] = {}

    def _cache_key(self, user_id: int, chat_id: int) -> str:
        return f"{user_id}:{chat_id}"

    async def get_warning_count(self, user_id: int, chat_id: int) -> int:
        """Return the stored count, or 0 when this user has no row in this chat."""
        cache_key = self._cache_key(user_id, chat_id)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return int(cached["warning_count"])

        async with self.database.engine.connect() as connection:
            row = (
                await connection.execute(
                    select(warnings.c.warning_count, warnings.c.banned).where(
                        warnings.c.telegram_user_id == user_id,
                        warnings.c.telegram_chat_id == chat_id,
                    )
                )
            ).mappings().first()
        if row is None:
            self._cache[cache_key] = {"warning_count": 0, "banned": False}
            return 0
        stored = int(row["warning_count"])
        self._cache[cache_key] = {"warning_count": stored, "banned": bool(row["banned"])}
        return stored

    async def add_warning(
        self,
        user_id: int,
        chat_id: int,
        username: str = "",
        reason: str = "content_violation",
    ) -> WarningResult:
        """Increase the count by one and record the reason."""
        current_count = await self.get_warning_count(user_id, chat_id)
        new_count, should_ban = warning_crosses_ban(current_count)
        now = datetime.now(timezone.utc)
        async with self.database.engine.begin() as connection:
            statement = insert(warnings).values(
                telegram_user_id=user_id,
                telegram_chat_id=chat_id,
                username=username,
                warning_count=new_count,
                last_reason=reason,
                last_warning=now,
                banned=should_ban,
            )
            statement = statement.on_conflict_do_update(
                index_elements=[
                    warnings.c.telegram_user_id,
                    warnings.c.telegram_chat_id,
                ],
                set_={
                    "username": statement.excluded.username,
                    "warning_count": statement.excluded.warning_count,
                    "last_reason": statement.excluded.last_reason,
                    "last_warning": statement.excluded.last_warning,
                    "banned": statement.excluded.banned,
                },
            )
            await connection.execute(statement)
        self._cache[self._cache_key(user_id, chat_id)] = {
            "warning_count": new_count,
            "banned": should_ban,
        }
        logger.info(
            "Warning added: user=%s, chat=%s, count=%s, ban=%s",
            user_id,
            chat_id,
            new_count,
            should_ban,
        )
        return WarningResult(
            warning_count=new_count,
            should_ban=should_ban,
            message=_warning_message(should_ban),
        )

    async def execute_ban(self, bot, user_id: int, chat_id: int) -> bool:
        """Ban the user in Telegram. The warnings row was already marked banned."""
        logger.info("Attempting to ban user %s from chat %s", user_id, chat_id)
        try:
            await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        except Exception:
            logger.exception("Failed to ban user %s from chat %s", user_id, chat_id)
            return False
        return True

    async def is_banned(self, user_id: int, chat_id: int) -> bool:
        """Return whether this user is marked banned in this chat."""
        await self.get_warning_count(user_id, chat_id)
        return bool(self._cache[self._cache_key(user_id, chat_id)]["banned"])


def _warning_message(should_ban: bool) -> str:
    if should_ban:
        return (
            "🚫 *BANNED*\n\n"
            "You have been *permanently removed* from the group.\n\n"
            "Reason: Repeated violations of community guidelines "
            "(spam, abuse, or inappropriate content).\n\n"
            "This was your 2nd violation. This action is logged."
        )
    return (
        "⚠️ *WARNING - FIRST AND FINAL*\n\n"
        "Your message was *deleted* for containing inappropriate content "
        "(spam, abuse, or policy violation).\n\n"
        "🚨 *You are now being tracked:*\n"
        "• This warning is logged permanently\n"
        "• Your user ID is recorded\n"
        "• *NEXT violation = PERMANENT BAN*\n\n"
        "This is your only warning. Follow community guidelines."
    )
