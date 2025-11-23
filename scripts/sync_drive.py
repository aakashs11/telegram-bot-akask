#!/usr/bin/env python3
"""
Script to manually trigger Google Drive sync.
Usage: python scripts/sync_drive.py
"""

import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_bot.services import DriveService, SyncService
from config.settings import DRIVE_FOLDER_ID

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    if not DRIVE_FOLDER_ID:
        logger.error("❌ DRIVE_FOLDER_ID is not set in .env or settings.py")
        logger.info("Please set it to the ID of the Google Drive folder you want to sync.")
        return

    logger.info("🚀 Starting Drive Sync...")
    
    try:
        drive_service = DriveService()
        sync_service = SyncService(drive_service)
        
        sync_service.sync_drive_to_index()
        
        logger.info("✅ Sync completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")

if __name__ == "__main__":
    main()
