"""
Sync Service.
Syncs files from Google Drive to the local index.json file.
"""

import json
import logging
import re
from typing import List, Dict, Any
from telegram_bot.services.drive_service import DriveService
from config.settings import DRIVE_FOLDER_ID, DRIVE_CONFIG_FOLDER_NAME, get_sheet
from utils.gspread_logging import log_drive_changes_batch

logger = logging.getLogger(__name__)

class SyncService:
    """
    Service to sync Drive files to index.json (stored in Drive).
    """
    
    def __init__(self, drive_service: DriveService):
        self.drive_service = drive_service
        self.index_filename = "index.json"

    def sync_drive_to_index(self):
        """
        Main sync function.
        1. Fetch all files and folders from Drive.
        2. Parse metadata using strict folder structure.
        3. Clear and rewrite 'Index' and 'Folders' tabs in Google Sheet.
        """
        if not DRIVE_FOLDER_ID:
            logger.warning("DRIVE_FOLDER_ID not set. Skipping sync.")
            return
            
        logger.info("Starting Drive sync...")
        
        # 1. Get current files from Drive
        current_files = self.drive_service.list_files_in_folder(DRIVE_FOLDER_ID)
        logger.info(f"Found {len(current_files)} files in Drive.")
        
        processed_rows = []
        folder_rows = []
        
        # 2. Process files and folders
        for file in current_files:
            if file['mimeType'] == 'application/vnd.google-apps.folder':
                # Track folder metadata
                path = file.get('path', '')
                if path:
                    folder_url = f"https://drive.google.com/drive/folders/{file['id']}"
                    # Format: Path, FolderID, URL
                    folder_rows.append([path, file['id'], folder_url])
                continue
                
            # Path comes from DriveService, e.g., "Class 12/AI/Notes/Unit 1"
            metadata = self._parse_metadata(file['name'], file.get('path', ''))
            
            if metadata:
                # Row format: Title, Link, Level, Subject, Type, Topic, FileID
                processed_rows.append([
                    file['name'],
                    file['webViewLink'],
                    metadata['level'],
                    metadata['subject'],
                    metadata['type'],
                    metadata['topic'],
                    file['id']
                ])
        
        # 3. Write to Google Sheet
        sh = get_sheet()
        if sh:
            try:
                # Update Index Tab (files)
                try:
                    worksheet = sh.worksheet("Index")
                    worksheet.clear()
                except:
                    worksheet = sh.add_worksheet(title="Index", rows=1000, cols=7)
                
                # Header
                headers = ["Title", "Link", "Level", "Subject", "Type", "Topic", "File ID"]
                
                # Batch update
                data = [headers] + processed_rows
                worksheet.update(range_name=f"A1:G{len(data)}", values=data)
                
                # Format header (bold)
                worksheet.format("A1:G1", {"textFormat": {"bold": True}})
                
                logger.info(f"Sync complete. Wrote {len(processed_rows)} rows to 'Index' sheet.")
                
                # Update Folders Tab
                try:
                    folder_sheet = sh.worksheet("Folders")
                    folder_sheet.clear()
                except:
                    folder_sheet = sh.add_worksheet(title="Folders", rows=1000, cols=3)
                
                folder_headers = ["Path", "Folder ID", "URL"]
                folder_data = [folder_headers] + folder_rows
                folder_sheet.update(range_name=f"A1:C{len(folder_data)}", values=folder_data)
                folder_sheet.format("A1:C1", {"textFormat": {"bold": True}})
                
                logger.info(f"Wrote {len(folder_rows)} folders to 'Folders' sheet.")
                
            except Exception as e:
                logger.error(f"Failed to update sheets: {e}")

    def _parse_metadata(self, filename: str, path: str = "") -> Dict[str, str]:
        """
        Extract metadata based on strict folder hierarchy:
        Level (Class) > Subject > Type > Topic (Optional)
        """
        if not path:
            return None
            
        parts = path.split('/')
        
        # Initialize defaults
        level = "General"
        subject = "General"
        res_type = "Other"
        topic = ""
        
        # Heuristic: We expect at least 2 levels (Level/Subject)
        # Example: "Class 12/AI/Notes/Unit 1" -> parts = ["Class 12", "AI", "Notes", "Unit 1"]
        
        if len(parts) >= 1:
            level = parts[0] # e.g., "Class 12", "College"
            
        if len(parts) >= 2:
            subject = parts[1] # e.g., "AI", "CS", "IP"
            
        if len(parts) >= 3:
            res_type = parts[2] # e.g., "Notes", "Books"
            
        if len(parts) >= 4:
            # Join all remaining parts as the topic
            # e.g., "Class 12/AI/Notes/Unit 1/Chapter 1" -> "Unit 1 - Chapter 1"
            topic = " - ".join(parts[3:])
            
        return {
            "level": level,
            "subject": subject,
            "type": res_type,
            "topic": topic
        }
