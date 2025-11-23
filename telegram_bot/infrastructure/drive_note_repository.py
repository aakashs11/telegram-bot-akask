"""
Drive Note Repository.
Implements NoteRepository using Google Drive as the storage backend.
"""

import json
import logging
from typing import List, Optional
from telegram_bot.domain.notes import Note, NoteRepository
from telegram_bot.services.drive_service import DriveService
from config.settings import get_sheet

logger = logging.getLogger(__name__)

class DriveNoteRepository(NoteRepository):
    """
    Repository that stores notes in the 'Index' tab of the Google Sheet.
    """
    
    def __init__(self, drive_service: DriveService):
        self.drive_service = drive_service # Kept for future use (e.g. direct downloads)
        self._cache: List[Note] = []
        self._cache_loaded = False

    async def get_all_notes(self) -> List[Note]:
        """Fetch notes from Sheet (with caching)"""
        if self._cache_loaded:
            return self._cache
            
        return await self._refresh_cache()

    async def _refresh_cache(self) -> List[Note]:
        """Read 'Index' sheet and update cache"""
        try:
            sh = get_sheet()
            if not sh:
                logger.error("Could not connect to Google Sheet")
                return []
                
            try:
                worksheet = sh.worksheet("Index")
            except:
                logger.warning("'Index' sheet not found. Run sync first.")
                return []
                
            # Get all values (list of lists)
            rows = worksheet.get_all_values()
            
            if not rows or len(rows) < 2:
                self._cache = []
                return []
                
            # Skip header row
            data_rows = rows[1:]
            
            self._cache = []
            for row in data_rows:
                # Expected: Title, Link, Level, Subject, Type, Topic, File ID
                if len(row) < 6:
                    continue
                    
                title = row[0]
                link = row[1]
                level = row[2]
                subject = row[3]
                res_type = row[4]
                topic = row[5]
                
                # Create Note object
                # Mapping:
                # Title -> Title
                # Content -> "{Level} {Subject} {Type} - {Topic}"
                # URL -> Link
                # Tags -> [Level, Subject, Type, Topic]
                
                note = Note(
                    id=title, # Use title as ID
                    title=title,
                    content=f"{level} {subject} {res_type} - {topic}",
                    url=link,
                    tags=[level, subject, res_type, topic]
                )
                self._cache.append(note)
            
            self._cache_loaded = True
            logger.info(f"Loaded {len(self._cache)} notes from Sheet.")
            return self._cache
            
        except Exception as e:
            logger.error(f"Failed to fetch notes from Sheet: {e}")
            return []

    async def add_note(self, note: Note) -> None:
        """
        Add a note. 
        WARNING: This is for manual additions. 
        Drive Sync usually overwrites this, so we should be careful.
        For now, we'll just update the cache and try to upload.
        """
        # Ensure cache is loaded
        if not self._cache_loaded:
            await self._refresh_cache()
            
        self._cache.append(note)
        
        # Convert back to Drive JSON format
        drive_notes = []
        for n in self._cache:
            drive_notes.append({
                "title": n.title,
                "link": n.url,
                "class": n.tags[0] if len(n.tags) > 0 else "",
                "subject": n.tags[1] if len(n.tags) > 1 else "",
                "type": n.tags[2] if len(n.tags) > 2 else ""
            })
            
        # Upload
        try:
            config_folder_id = self.drive_service.get_or_create_folder(
                DRIVE_CONFIG_FOLDER_NAME, parent_id=DRIVE_FOLDER_ID
            )
            data = {"notes": drive_notes}
            self.drive_service.upload_json_file(self.index_filename, data, config_folder_id)
        except Exception as e:
            logger.error(f"Failed to save note to Drive: {e}")

    async def get_note_by_id(self, note_id: str) -> Optional[Note]:
        notes = await self.get_all_notes()
        for note in notes:
            if note.id == note_id:
                return note
        return None
