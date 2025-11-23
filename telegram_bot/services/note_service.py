import uuid
from typing import List, Optional
from telegram_bot.domain.notes import Note, NoteRepository

class NoteService:
    def __init__(self, repository: NoteRepository):
        self.repository = repository

    async def get_all_notes(self) -> List[Note]:
        return await self.repository.get_all_notes()

    async def add_note(self, title: str, content: str, url: Optional[str] = None, tags: List[str] = None) -> Note:
        note = Note(
            id=str(uuid.uuid4()),
            title=title,
            content=content,
            url=url,
            tags=tags or []
        )
        await self.repository.add_note(note)
        return note
