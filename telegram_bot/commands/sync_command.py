from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.services.sync_service import SyncService
from config.settings import ADMIN_USER_IDS
import logging

logger = logging.getLogger(__name__)

class SyncCommand:
    def __init__(self, sync_service: SyncService):
        self.sync_service = sync_service

    async def sync_drive(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Triggers a manual Drive sync."""
        user_id = update.effective_user.id
        if user_id not in ADMIN_USER_IDS:
            await update.message.reply_text("🚫 Only bot admins can run sync.")
            return
        
        status_msg = await update.message.reply_text("🔄 Starting Drive sync... This may take a moment.")
        
        try:
            # Run sync in a separate thread to avoid blocking
            import asyncio
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.sync_service.sync_drive_to_index)
            
            await status_msg.edit_text("✅ Sync complete! The Index sheet has been updated.")
            
        except Exception as e:
            logger.error(f"Manual sync failed: {e}")
            await status_msg.edit_text(f"❌ Sync failed: {str(e)}")
