"""Student profile table. One row per Telegram user.

This matches the UserProfiles Google Sheet. The bot still reads and writes
that sheet. This table is the Postgres shape those rows will be copied into.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    SmallInteger,
    Table,
    Text,
)

from telegram_bot.infrastructure.postgres_interaction_repository import metadata

students = Table(
    "students",
    metadata,
    Column(
        "telegram_user_id",
        BigInteger,
        primary_key=True,
        nullable=False,
        autoincrement=False,
    ),
    Column("username", Text, nullable=False, server_default=""),
    Column("current_class", SmallInteger, nullable=True),
    Column("preferred_subject", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_updated", DateTime(timezone=True), nullable=False),
    Column("class_updated_year", Integer, nullable=False),
    CheckConstraint(
        "current_class IS NULL OR current_class IN (10, 11, 12)",
        name="ck_students_current_class",
    ),
    CheckConstraint(
        "preferred_subject IS NULL OR preferred_subject IN ('AI', 'CS', 'IT', 'IP')",
        name="ck_students_preferred_subject",
    ),
)
