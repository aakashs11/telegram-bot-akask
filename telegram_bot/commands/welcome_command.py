"""
WelcomeCommand: Handles welcoming new members when they join a group.

Sends an auto-deleting welcome message with an inline button to start
a private conversation with the bot for notes and study materials.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.common import schedule_message_deletion

logger = logging.getLogger(__name__)


class WelcomeCommand:
    """
    Command handler for welcoming new group members.
    
    Sends a welcome message with full intro (notes, videos, chat capabilities)
    and an inline button to start the bot in private. Message auto-deletes
    after 30 seconds to keep the group clean.
    """

    async def on_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle new members joining a group.
        
        Args:
            update: Telegram update containing new chat members info
            context: Bot context with bot instance and utilities
            
        Returns:
            None
        """
        # Skip if no new members in the update
        if not update.message or not update.message.new_chat_members:
            return

        bot_id = context.bot.id
        bot_username = context.bot.username

        # Process each new member
        for new_member in update.message.new_chat_members:
            # Skip if the new member is the bot itself
            if new_member.id == bot_id:
                logger.info("Bot was added to a group, skipping welcome for self.")
                continue

            # Build the welcome message
            welcome_text = (
                f"👋 Welcome, {new_member.first_name}!\n\n"
                "I'm **ASK.ai**, your AI study buddy! Here's what I can help you with:\n\n"
                "📚 **Notes & Study Materials** - Class notes, books, sample papers\n"
                "🎥 **Video Tutorials** - Educational videos on any topic\n"
                "💬 **Chat with me** - Just ask naturally, no commands needed!\n\n"
                "Tap the button below to start chatting with me privately:"
            )

            # Create inline button with deep link to start bot
            deep_link = f"https://t.me/{bot_username}?start=notes"
            keyboard = [[
                InlineKeyboardButton(
                    "💬 Start Chat with ASK.ai",
                    url=deep_link
                )
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send welcome message
            welcome_msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=welcome_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

            # Schedule message deletion after 30 seconds
            schedule_message_deletion(context.bot, welcome_msg.chat_id, welcome_msg.message_id)

            logger.info(f"Sent welcome message to {new_member.first_name} (ID: {new_member.id})")
