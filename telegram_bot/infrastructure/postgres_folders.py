"""Drive folder table. One row per folder in the Folders sheet.

The bot looks up a path such as Class 10/AI/Notes and returns the URL.
The folder itself stays in Google Drive. Nothing in the bot reads this
table yet.
"""

from __future__ import annotations

from sqlalchemy import Column, Table, Text, UniqueConstraint

from telegram_bot.infrastructure.postgres_interaction_repository import metadata

folders = Table(
    "folders",
    metadata,
    Column("drive_folder_id", Text, primary_key=True, nullable=False),
    Column("path", Text, nullable=False),
    Column("url", Text, nullable=False, server_default=""),
    UniqueConstraint("path", name="uq_folders_path"),
)
