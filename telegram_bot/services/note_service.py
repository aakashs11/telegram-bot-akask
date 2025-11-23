import uuid
from typing import List, Optional
from telegram_bot.domain.notes import Note, NoteRepository
from config.settings import get_sheet

class NoteService:
    def __init__(self, repository: NoteRepository):
        self.repository = repository

    async def get_all_notes(self) -> List[Note]:
        return await self.repository.get_all_notes()
    
    async def get_folder_link(
        self,
        class_num: Optional[int] = None,
        subject: Optional[str] = None,
        resource_type: Optional[str] = "Notes",
        topic: Optional[str] = None
    ) -> Optional[str]:
        """
        Get Google Drive folder link for a specific path.
        
        Args:
            class_num: Class number (10, 11, 12)
            subject: Subject code (AI, IT, CS, IP)
            resource_type: Type of resource (Notes, Books, etc.)
            topic: Optional topic/subfolder (e.g., "NLP", "Computer Vision")
            
        Returns:
            Folder URL if found, None otherwise
        """
        if not class_num or not subject:
            return None
            
        # Build expected path
        # Format: "Class 10/AI/Notes" or "Class 10/AI/Notes/NLP"
        expected_path = f"Class {class_num}/{subject}/{resource_type}"
        if topic:
            expected_path += f"/{topic}"
        
        # Query Folders sheet
        sh = get_sheet()
        if not sh:
            return None
            
        try:
            folder_sheet = sh.worksheet("Folders")
            all_folders = folder_sheet.get_all_values()
            
            # Skip header
            for row in all_folders[1:]:
                if len(row) >= 3:
                    path, folder_id, url = row[0], row[1], row[2]
                    # Match exact path or startswith for base folders
                    if path == expected_path or (not topic and path.startswith(expected_path)):
                        return url
                        
        except Exception as e:
            # Folders sheet doesn't exist yet
            pass
            
        return None
    
    async def get_notes(
        self,
        class_num: Optional[int] = None,
        subject: Optional[str] = None,
        resource_type: Optional[str] = None,
        topic: Optional[str] = None
    ) -> List[Note]:
        """
        Get notes filtered by class, subject, and/or resource type.
        
        Args:
            class_num: Class number (10, 11, 12)
            subject: Subject code (AI, IT, CS, IP)
            resource_type: Type of resource (Notes, Books, etc.)
            topic: Optional topic filter
            
        Returns:
            Filtered list of notes
        """
        all_notes = await self.get_all_notes()
        
        # Filter based on criteria
        # Note: The tags in Note objects contain [class, subject, type, topic]
        filtered = []
        for note in all_notes:
            if len(note.tags) < 3:
                continue
                
            note_class = note.tags[0] if len(note.tags) > 0 else ""
            note_subject = note.tags[1] if len(note.tags) > 1 else ""
            note_type = note.tags[2] if len(note.tags) > 2 else ""
            note_topic = note.tags[3] if len(note.tags) > 3 else ""
            
            # Match filters
            if class_num and f"Class {class_num}" != note_class and str(class_num) != note_class:
                continue
            if subject and subject != note_subject:
                continue
            if resource_type and resource_type != note_type:
                continue
            if topic and topic.lower() not in note_topic.lower():
                continue
                
            filtered.append(note)
        
        return filtered

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
