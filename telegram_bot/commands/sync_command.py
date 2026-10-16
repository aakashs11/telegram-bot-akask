from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.services.catalog_sync import replace_content_catalog
from telegram_bot.services.sync_service import SyncService
from config.settings import ADMIN_USER_IDS
import logging

logger = logging.getLogger(__name__)

class SyncCommand:
    def __init__(self, sync_service: SyncService, catalog_database=None, note_repository=None):
        self.sync_service = sync_service
        self.catalog_database = catalog_database
        self.note_repository = note_repository

    async def sync_drive(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Triggers a manual Drive sync."""
        user_id = update.effective_user.id
        if user_id not in ADMIN_USER_IDS:
            await update.message.reply_text("🚫 Only bot admins can run sync.")
            return
        
        status_msg = await update.message.reply_text("🔄 Starting Drive sync... This may take a moment.")
        
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            if self.catalog_database is not None:
                snapshot = await loop.run_in_executor(None, self.sync_service.build_snapshot)
                await replace_content_catalog(self.catalog_database, snapshot)
                if self.note_repository is not None:
                    self.note_repository.clear_cache()
                await status_msg.edit_text(
                    "✅ Sync complete! "
                    f"{len(snapshot.items)} files and {len(snapshot.folders)} folders "
                    "are in Postgres."
                )
                return
            await loop.run_in_executor(None, self.sync_service.sync_drive_to_index)
            await status_msg.edit_text("✅ Sync complete! The Index sheet has been updated.")
            
        except Exception as e:
            logger.error(f"Manual sync failed: {e}")
            await status_msg.edit_text(f"❌ Sync failed: {str(e)}")
