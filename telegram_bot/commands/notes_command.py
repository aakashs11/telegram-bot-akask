import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus
from telegram_bot.services.note_service import NoteService

logger = logging.getLogger(__name__)

class NotesCommand:
    def __init__(self, note_service: NoteService):
        self.note_service = note_service

    async def list_notes(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle /notes command:
        - In groups: Delete command, show inline button, auto-cleanup message
        - In private: Ignore command (user should chat naturally with bot)
        """
        chat_type = update.effective_chat.type
        
        # GROUP/SUPERGROUP: Clean interaction with inline button
        if chat_type in ['group', 'supergroup']:
            try:
                # Delete the /notes command message to keep group clean
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=update.message.message_id
                )
            except Exception as e:
                logger.warning(f"Could not delete message (bot might not be admin): {e}")
            
            # Send inline button for private chat
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            bot_username = context.bot.username
            deep_link = f"https://t.me/{bot_username}?start=notes"
            
            keyboard = [[
                InlineKeyboardButton(
                    "📚 Get Notes in Private Chat", 
                    url=deep_link
                )
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send button message
            button_msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"👤 @{update.effective_user.username or update.effective_user.first_name}, tap the button below to get notes privately:",
                reply_markup=reply_markup
            )
            
            # Schedule message deletion after 30 seconds using background task
            import asyncio
            async def auto_delete():
                await asyncio.sleep(30)
                try:
                    await context.bot.delete_message(
                        chat_id=button_msg.chat_id,
                        message_id=button_msg.message_id
                    )
                    logger.info(f"Auto-deleted button message {button_msg.message_id}")
                except Exception as e:
                    logger.warning(f"Could not auto-delete button: {e}")
            
            # Start background task (fire and forget)
            import asyncio
            asyncio.ensure_future(auto_delete())
            
            return
        
        # PRIVATE CHAT: Don't interfere with conversational flow
        # The /notes command in private chat should be ignored
        # Users should just ask: "I need Class 12 CS notes"
        # This keeps the GPT conversational experience intact
        await update.message.reply_text(
            "💬 Just tell me what you need! No need for commands.\n\n"
            "For example, try:\n"
            "• \"I need Class 12 CS notes\"\n"
            "• \"Show me AI study materials for Class 10\"\n"
            "• \"Find Python videos\""
        )

    async def add_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # Check if user is admin
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            if member.status not in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]:
                await update.message.reply_text("🚫 Only admins can add notes.")
                return
        except Exception:
            # If private chat or error, might default to allowing or denying. 
            # For safety, let's deny if we can't verify, or maybe allow if it's the owner defined in env?
            # For now, strictly enforce group admin check.
            await update.message.reply_text("🚫 Could not verify admin status.")
            return

        # Parse arguments: /addnote Title | Content | URL (optional)
        args_text = " ".join(context.args)
        if not args_text:
            await update.message.reply_text("Usage: /addnote Title | Content | URL")
            return

        parts = [p.strip() for p in args_text.split('|')]
        if len(parts) < 2:
            await update.message.reply_text("⚠️ Format: /addnote Title | Content | URL (optional)")
            return

        title = parts[0]
        content = parts[1]
        url = parts[2] if len(parts) > 2 else None

        await self.note_service.add_note(title, content, url)
        await update.message.reply_text(f"✅ Note '{title}' added successfully!")
