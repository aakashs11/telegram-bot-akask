"""Moderation strikes. One row per Telegram user in one chat.

This matches the Warnings sheet: user_id, chat_id, username, warning_count,
last_reason, last_warning, banned. A person can be warned in more than one
group, so both ids are the primary key.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    Table,
    Text,
)

from telegram_bot.infrastructure.postgres_interaction_repository import metadata

warnings = Table(
    "warnings",
    metadata,
    Column(
        "telegram_user_id",
        BigInteger,
        primary_key=True,
        nullable=False,
        autoincrement=False,
    ),
    Column(
        "telegram_chat_id",
        BigInteger,
        primary_key=True,
        nullable=False,
        autoincrement=False,
    ),
    Column("username", Text, nullable=False, server_default=""),
    Column("warning_count", Integer, nullable=False),
    Column("last_reason", Text, nullable=False, server_default=""),
    Column("last_warning", DateTime(timezone=True), nullable=False),
    Column("banned", Boolean, nullable=False, server_default="false"),
    CheckConstraint(
        "warning_count >= 0",
        name="ck_warnings_count_nonnegative",
    ),
)
