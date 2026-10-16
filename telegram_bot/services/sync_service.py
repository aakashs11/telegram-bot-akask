"""
Sync Service.
Syncs files from Google Drive to the local index.json file.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any
from telegram_bot.services.drive_service import DriveService
from config.settings import DRIVE_FOLDER_ID, get_sheet

logger = logging.getLogger(__name__)

FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


@dataclass(frozen=True, slots=True)
class CatalogSnapshot:
    """One Drive scan, ready to replace the catalog tables."""

    items: list[dict[str, str]] = field(default_factory=list)
    folders: list[dict[str, str]] = field(default_factory=list)
    skipped: int = 0
    duplicate_file_ids: int = 0
    duplicate_folder_ids: int = 0
    duplicate_paths: int = 0


def parse_catalog_metadata(path: str) -> Dict[str, str] | None:
    """Split a Drive path into level, subject, type, and topic.

    ``Class 12/AI/Notes/Computer Vision`` becomes level ``Class 12``,
    subject ``AI``, type ``Notes``, topic ``Computer Vision``.
    """
    if not path:
        return None

    parts = path.split("/")
    level = parts[0] if len(parts) >= 1 else "General"
    subject = parts[1] if len(parts) >= 2 else "General"
    res_type = parts[2] if len(parts) >= 3 else "Other"
    topic = " - ".join(parts[3:]) if len(parts) >= 4 else ""
    return {
        "level": level,
        "subject": subject,
        "type": res_type,
        "topic": topic,
    }


def catalog_from_drive_files(files: list[dict[str, Any]]) -> CatalogSnapshot:
    """Turn a Drive listing into catalog rows. The first id or path wins."""
    items: list[dict[str, str]] = []
    folders: list[dict[str, str]] = []
    seen_files: set[str] = set()
    seen_folder_ids: set[str] = set()
    seen_paths: set[str] = set()
    skipped = 0
    duplicate_file_ids = 0
    duplicate_folder_ids = 0
    duplicate_paths = 0

    for file in files:
        path = file.get("path", "") or ""
        file_id = str(file.get("id", "")).strip()
        if file.get("mimeType") == FOLDER_MIME_TYPE:
            if not path or not file_id:
                skipped += 1
                continue
            if file_id in seen_folder_ids:
                duplicate_folder_ids += 1
                continue
            if path in seen_paths:
                duplicate_paths += 1
                continue
            seen_folder_ids.add(file_id)
            seen_paths.add(path)
            folders.append(
                {
                    "drive_folder_id": file_id,
                    "path": path,
                    "url": f"https://drive.google.com/drive/folders/{file_id}",
                }
            )
            continue

        metadata = parse_catalog_metadata(path)
        if metadata is None or not file_id or not str(file.get("name", "")).strip():
            skipped += 1
            continue
        if file_id in seen_files:
            duplicate_file_ids += 1
            continue
        seen_files.add(file_id)
        items.append(
            {
                "drive_file_id": file_id,
                "title": file["name"],
                "link": file.get("webViewLink") or "",
                "level": metadata["level"],
                "subject": metadata["subject"],
                "resource_type": metadata["type"],
                "topic": metadata["topic"],
            }
        )

    return CatalogSnapshot(
        items=items,
        folders=folders,
        skipped=skipped,
        duplicate_file_ids=duplicate_file_ids,
        duplicate_folder_ids=duplicate_folder_ids,
        duplicate_paths=duplicate_paths,
    )

class SyncService:
    """
    Service to sync Drive files to index.json (stored in Drive).
    """
    
    def __init__(self, drive_service: DriveService):
        self.drive_service = drive_service
        self.index_filename = "index.json"

    def build_snapshot(self) -> CatalogSnapshot:
        """List Drive and return the rows a Postgres replace would write."""
        if not DRIVE_FOLDER_ID:
            raise ValueError("DRIVE_FOLDER_ID is not set")
        current_files = self.drive_service.list_files_in_folder(DRIVE_FOLDER_ID)
        logger.info("Found %s files in Drive.", len(current_files))
        return catalog_from_drive_files(current_files)

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

    def _parse_metadata(self, filename: str, path: str = "") -> Dict[str, str] | None:
        """Extract metadata from the Drive folder path. The filename is unused."""
        del filename
        return parse_catalog_metadata(path)
