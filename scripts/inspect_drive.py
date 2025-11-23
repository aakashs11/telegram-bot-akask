#!/usr/bin/env python3
"""
Script to inspect Google Drive folder structure.
Usage: python scripts/inspect_drive.py
"""

import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_bot.services import DriveService
from config.settings import DRIVE_FOLDER_ID

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def print_tree(files, parent_id, indent=""):
    """Recursive function to print file tree"""
    # Find files with this parent
    children = [f for f in files if parent_id in f.get('parents', [])]
    
    for file in children:
        is_folder = file['mimeType'] == 'application/vnd.google-apps.folder'
        icon = "📁" if is_folder else "📄"
        print(f"{indent}{icon} {file['name']} (ID: {file['id']})")
        
        if is_folder:
            print_tree(files, file['id'], indent + "  ")

def main():
    if not DRIVE_FOLDER_ID:
        logger.error("❌ DRIVE_FOLDER_ID is not set.")
        return

    logger.info(f"🔍 Inspecting Drive Folder: {DRIVE_FOLDER_ID}")
    
    try:
        drive_service = DriveService()
        # Get ALL files recursively (our list_files_in_folder does this)
        files = drive_service.list_files_in_folder(DRIVE_FOLDER_ID)
        
        print("\n--- Drive Structure ---\n")
        print_tree(files, DRIVE_FOLDER_ID)
        print("\n-----------------------\n")
        
    except Exception as e:
        logger.error(f"❌ Inspection failed: {e}")

if __name__ == "__main__":
    main()
