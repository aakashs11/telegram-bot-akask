from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import List, Optional

@dataclass
class Note:
    id: str
    title: str
    content: str
    url: Optional[str] = None
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

class NoteRepository(ABC):
    @abstractmethod
    async def get_all_notes(self) -> List[Note]:
        pass

    @abstractmethod
    async def add_note(self, note: Note) -> None:
        pass

    @abstractmethod
    async def get_note_by_id(self, note_id: str) -> Optional[Note]:
        pass
