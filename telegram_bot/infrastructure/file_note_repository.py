import json
import os
import aiofiles
from typing import List, Optional
from telegram_bot.domain.notes import Note, NoteRepository

class FileNoteRepository(NoteRepository):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump([], f)

    async def get_all_notes(self) -> List[Note]:
        async with aiofiles.open(self.file_path, 'r') as f:
            content = await f.read()
            data = json.loads(content)
            return [Note(**item) for item in data]

    async def add_note(self, note: Note) -> None:
        notes = await self.get_all_notes()
        notes.append(note)
        await self._save_notes(notes)

    async def get_note_by_id(self, note_id: str) -> Optional[Note]:
        notes = await self.get_all_notes()
        for note in notes:
            if note.id == note_id:
                return note
        return None

    async def _save_notes(self, notes: List[Note]) -> None:
        data = [
            {
                "id": note.id,
                "title": note.title,
                "content": note.content,
                "url": note.url,
                "tags": note.tags
            }
            for note in notes
        ]
        async with aiofiles.open(self.file_path, 'w') as f:
            await f.write(json.dumps(data, indent=2))
