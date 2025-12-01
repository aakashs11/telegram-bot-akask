"""
Centralized message sending utilities for Telegram bot.

Provides unified message sending with automatic splitting and markdown support.
Follows Single Responsibility: only handles message delivery.
"""

import logging
from typing import Optional, List
from telegram import Update, Message
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from utils.formatting import split_message

logger = logging.getLogger(__name__)


async def send_response(
    update: Update,
    text: str,
    parse_mode: str = "Markdown",
    disable_preview: bool = True
) -> List[Message]:
    """
    Send a response message with automatic splitting for long messages.
    
    Args:
        update: Telegram Update object
        text: Message text to send
        parse_mode: Telegram parse mode (default: Markdown)
        disable_preview: Disable link previews
        
    Returns:
        List of sent Message objects
    """
    sent_messages = []
    chunks = split_message(text)
    
    for i, chunk in enumerate(chunks):
        try:
            if i == 0:
                # First message replies to user
                msg = await update.message.reply_text(
                    chunk,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_preview
                )
            else:
                # Subsequent messages are standalone
                msg = await update.effective_chat.send_message(
                    chunk,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_preview
                )
            sent_messages.append(msg)
            
        except TelegramError as e:
            logger.error(f"Failed to send message chunk {i+1}: {e}")
            # Fallback: send without parse_mode
            try:
                msg = await update.message.reply_text(chunk)
                sent_messages.append(msg)
            except TelegramError:
                pass  # Already logged above
    
    return sent_messages


async def send_to_user(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    text: str,
    parse_mode: str = "Markdown"
) -> Optional[Message]:
    """
    Send a direct message to a user by ID.
    
    Args:
        context: Bot context
        user_id: Target user's Telegram ID
        text: Message text
        parse_mode: Telegram parse mode
        
    Returns:
        Sent Message object or None if failed
    """
    try:
        return await context.bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode=parse_mode
        )
    except TelegramError as e:
        logger.warning(f"Could not send message to user {user_id}: {e}")
        return None


async def send_plain(update: Update, text: str) -> Optional[Message]:
    """
    Send a plain text message without formatting.
    
    Args:
        update: Telegram Update object
        text: Plain text message
        
    Returns:
        Sent Message object or None if failed
    """
    try:
        return await update.message.reply_text(text)
    except TelegramError as e:
        logger.error(f"Failed to send plain message: {e}")
        return None

