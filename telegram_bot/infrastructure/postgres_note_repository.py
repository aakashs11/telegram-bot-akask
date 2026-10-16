"""Notes catalog and folder links stored in Postgres.

File bytes stay in Google Drive. This repository reads the copied
content_items and folders tables.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy import select

from telegram_bot.domain.catalog_names import canonical_resource_type, catalog_paths_match
from telegram_bot.domain.notes import Note, NoteRepository
from telegram_bot.infrastructure.database import Database
from telegram_bot.infrastructure.postgres_content_items import content_items
from telegram_bot.infrastructure.postgres_folders import folders

logger = logging.getLogger(__name__)


def note_from_catalog(
    title: str,
    link: str,
    level: str,
    subject: str,
    resource_type: str,
    topic: str,
) -> Note:
    """Match the Note shape the sheet repository already returns."""
    resource_type = canonical_resource_type(resource_type)
    return Note(
        id=title,
        title=title,
        content=f"{level} {subject} {resource_type} - {topic}",
        url=link,
        tags=[level, subject, resource_type, topic],
    )


def choose_folder_url(
    rows: list[tuple[str, str]],
    expected_path: str,
    topic: Optional[str],
) -> Optional[str]:
    """Pick one folder URL for a class/subject/type path.

    An exact path wins. When the request has no topic, a longer path that
    starts with the requested folder also matches, and the shortest match
    is the folder the student asked for.
    """
    matches = [
        (path, url)
        for path, url in rows
        if catalog_paths_match(path, expected_path, topic)
    ]
    if not matches:
        return None
    matches.sort(key=lambda item: (len(item[0]), item[0]))
    return matches[0][1]


class PostgresNoteRepository(NoteRepository):
    """Read the content catalog and folder paths from Postgres."""

    def __init__(self, database: Database):
        self.database = database
        self._cache: List[Note] = []
        self._cache_loaded = False

    def clear_cache(self) -> None:
        """Drop the loaded catalog so the next read sees a fresh sync."""
        self._cache = []
        self._cache_loaded = False

    async def get_all_notes(self) -> List[Note]:
        if self._cache_loaded:
            return self._cache
        async with self.database.engine.connect() as connection:
            rows = (
                await connection.execute(
                    select(
                        content_items.c.title,
                        content_items.c.link,
                        content_items.c.level,
                        content_items.c.subject,
                        content_items.c.resource_type,
                        content_items.c.topic,
                    ).order_by(content_items.c.title)
                )
            ).all()
        self._cache = [
            note_from_catalog(title, link, level, subject, resource_type, topic)
            for title, link, level, subject, resource_type, topic in rows
        ]
        self._cache_loaded = True
        logger.info("Loaded %s notes from content_items.", len(self._cache))
        return self._cache

    async def get_folder_url(
        self,
        class_num: Optional[int] = None,
        subject: Optional[str] = None,
        resource_type: Optional[str] = "Notes",
        topic: Optional[str] = None,
    ) -> Optional[str]:
        """Return the Drive folder URL for Class/Subject/Type[/Topic]."""
        if not class_num or not subject:
            return None
        expected = f"Class {class_num}/{subject}/{resource_type or 'Notes'}"
        if topic:
            expected = f"{expected}/{topic}"
        async with self.database.engine.connect() as connection:
            rows = (await connection.execute(select(folders.c.path, folders.c.url))).all()
        return choose_folder_url(rows, expected, topic)

    async def add_note(self, note: Note) -> None:
        """Store a manually added note. Drive sync does not use this path."""
        tags = note.tags or []
        if not self._cache_loaded:
            await self.get_all_notes()
        self._cache.append(note)
        async with self.database.engine.begin() as connection:
            await connection.execute(
                content_items.insert().values(
                    drive_file_id=note.id,
                    title=note.title,
                    link=note.url or "",
                    level=tags[0] if len(tags) > 0 else "",
                    subject=tags[1] if len(tags) > 1 else "",
                    resource_type=tags[2] if len(tags) > 2 else "",
                    topic=tags[3] if len(tags) > 3 else "",
                )
            )

    async def get_note_by_id(self, note_id: str) -> Optional[Note]:
        notes = await self.get_all_notes()
        for note in notes:
            if note.id == note_id:
                return note
        return None
