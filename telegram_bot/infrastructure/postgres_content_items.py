"""Content catalog table. One row per Google Drive file.

This matches the Index sheet. The PDF or other file stays in Drive.
The bot still reads the sheet. This table is the Postgres shape those
rows will be copied into.
"""

from __future__ import annotations

from sqlalchemy import Column, Index, Table, Text

from telegram_bot.infrastructure.postgres_interaction_repository import metadata

content_items = Table(
    "content_items",
    metadata,
    Column("drive_file_id", Text, primary_key=True, nullable=False),
    Column("title", Text, nullable=False),
    Column("link", Text, nullable=False, server_default=""),
    Column("level", Text, nullable=False),
    Column("subject", Text, nullable=False),
    Column("resource_type", Text, nullable=False),
    Column("topic", Text, nullable=False, server_default=""),
    Index(
        "ix_content_items_level_subject_type",
        "level",
        "subject",
        "resource_type",
    ),
)
