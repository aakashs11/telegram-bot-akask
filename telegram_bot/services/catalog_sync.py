"""Replace the Postgres catalog from one Drive snapshot.

The Google Sheet is not touched. An empty snapshot is refused so a Drive
API error cannot delete the copied rows. The delete and insert run in
one transaction.
"""

from __future__ import annotations

from sqlalchemy import delete, insert

from telegram_bot.infrastructure.database import Database
from telegram_bot.infrastructure.postgres_content_items import content_items
from telegram_bot.infrastructure.postgres_folders import folders
from telegram_bot.services.sync_service import CatalogSnapshot


async def replace_content_catalog(database: Database, snapshot: CatalogSnapshot) -> None:
    """Replace content_items and folders with this snapshot."""
    if not snapshot.items or not snapshot.folders:
        raise ValueError(
            "refusing to replace the catalog from an empty Drive snapshot: "
            f"{len(snapshot.items)} files, {len(snapshot.folders)} folders"
        )
    async with database.engine.begin() as connection:
        await connection.execute(delete(content_items))
        await connection.execute(delete(folders))
        await connection.execute(insert(content_items).values(snapshot.items))
        await connection.execute(insert(folders).values(snapshot.folders))
