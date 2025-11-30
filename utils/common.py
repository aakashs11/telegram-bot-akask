"""
Common utility functions used across the telegram bot.

This module contains shared utilities for conversation history management
and message scheduling operations.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

user_conversations = {}


def schedule_message_deletion(bot, chat_id: int, message_id: int, delay: int = 30) -> None:
    """
    Schedule a message for deletion after a specified delay.
    
    Fires and forgets an async task that waits for the delay period
    then attempts to delete the message. Errors are logged but not raised.
    
    Args:
        bot: Telegram bot instance (context.bot)
        chat_id: ID of the chat containing the message
        message_id: ID of the message to delete
        delay: Seconds to wait before deletion (default: 30)
        
    Returns:
        None
    """
    async def _delete_after_delay():
        await asyncio.sleep(delay)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info(f"Auto-deleted message {message_id} in chat {chat_id}")
        except Exception as e:
            logger.warning(f"Could not auto-delete message {message_id}: {e}")
    
    asyncio.ensure_future(_delete_after_delay())


def append_to_history(user_id, role, content):
    """
    Maintains a short conversation history per user.
    """
    if user_id not in user_conversations:
        user_conversations[user_id] = []

    user_conversations[user_id].append({"role": role, "content": content})

    MAX_HISTORY_SIZE = 3
    if len(user_conversations[user_id]) > MAX_HISTORY_SIZE:
        user_conversations[user_id] = user_conversations[user_id][-MAX_HISTORY_SIZE:]
