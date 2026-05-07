"""
Telegram bot message handlers.

Handles /start command and user messages with unified message sending.
Routes group messages to GroupOrchestrator, private messages to AgentService.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.runtime import ChatType
from utils.gspread_logging import log_interaction
from telegram_bot.services.message_service import send_response, send_plain

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command with optional deep link parameters."""
    args = context.args
    
    if args and args[0] == 'notes':
        # User clicked the button from a group to get notes
        welcome_message = (
            "👋 Hey! I'm ASK AI - your study buddy!\n\n"
            "I can help you find:\n"
            "📚 Notes, books & sample papers\n"
            "🎬 Video lessons from Aakash Sir\n\n"
            "Just tell me like you'd tell a friend:\n"
            "• \"I need Class 12 CS notes\"\n"
            "• \"Show me Python videos\"\n"
            "• \"Help me with NLP revision\"\n\n"
            "What are you studying today? 📖"
        )
    else:
        # Standard welcome for /start in private chat
        welcome_message = (
            "👋 Hey! I'm ASK AI - your study buddy!\n\n"
            "I can help you find:\n"
            "📚 Notes, books & sample papers\n"
            "🎬 Video lessons\n\n"
            "Just tell me what you need!"
        )
    
    await send_response(update, welcome_message)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle regular text messages.
    
    Routes to:
    - TelegramAdapter for platform parsing/delivery
    - ChatRuntime for shared private/group decision logic
    """
    # Guard: Skip if no message (edited messages, channel posts, etc.)
    if not update.message or not update.message.text:
        return
    
    try:
        runtime = context.application.bot_data.get("chat_runtime")
        adapter = context.application.bot_data.get("telegram_adapter")

        if not runtime or not adapter:
            logger.error("ChatRuntime or TelegramAdapter not initialized in bot_data")
            return

        chat_message = adapter.to_chat_message(update, context)
        if not chat_message:
            return

        logger.info(
            "📨 Message received: user=%s, chat=%s, platform=%s, type=%s",
            chat_message.platform_user_id,
            chat_message.platform_chat_id,
            chat_message.platform.value,
            chat_message.chat_type.value,
        )
        logger.debug("Message length: %s chars", len(chat_message.text))

        response = await runtime.handle(chat_message)

        if response.metadata.get("action") == "group_violation":
            await _handle_group_violation(update, context, chat_message)
            return

        await adapter.send_response(update, context, response)
        await _log_private_interaction(update, context, chat_message, response.text)

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await send_plain(update, "Sorry, I encountered an error. Please try again.")


async def _handle_group_violation(update, context, chat_message) -> None:
    group_orchestrator = context.application.bot_data.get("group_orchestrator")
    if not group_orchestrator:
        logger.error("GroupOrchestrator not initialized in bot_data")
        return

    await group_orchestrator.handle_violation(
        update=update,
        context=context,
        user_id=int(chat_message.platform_user_id),
        chat_id=int(chat_message.platform_chat_id),
        username=chat_message.username,
    )


async def _log_private_interaction(update, context, chat_message, response_text: str) -> None:
    if chat_message.chat_type != ChatType.PRIVATE or not response_text:
        return

    sh = context.application.bot_data.get("sh")
    if sh:
        try:
            log_interaction(
                sh,
                user_id=int(chat_message.platform_user_id),
                user_message=chat_message.text,
                bot_response=response_text,
                screener_output="",
                intent_output="agent",
                entities_output=""
            )
        except Exception as log_error:
            logger.warning(f"Failed to log interaction: {log_error}")
