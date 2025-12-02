"""
Telegram bot message handlers.

Handles /start command and user messages with unified message sending.
Routes group messages to GroupOrchestrator, private messages to AgentService.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

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
    - GroupOrchestrator for group/supergroup chats (moderation for ALL messages)
    - AgentService for private chats
    """
    # Guard: Skip if no message (edited messages, channel posts, etc.)
    if not update.message or not update.message.text:
        return
    
    try:
        user_message = update.message.text
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type
        
        # Get services from bot_data
        user_service = context.application.bot_data.get("user_service")
        
        if not user_service:
            logger.error("UserService not initialized in bot_data")
            return

        # === GROUP CHAT: Route to GroupOrchestrator ===
        if chat_type in ['group', 'supergroup']:
            await _handle_group_message(update, context, user_message, user_id)
            return
        
        # === PRIVATE CHAT: Use AgentService directly ===
        await _handle_private_message(update, context, user_message, user_id)
                
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await send_plain(update, "Sorry, I encountered an error. Please try again.")


async def _handle_group_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_message: str,
    user_id: int
) -> None:
    """
    Route ALL group messages to GroupOrchestrator.
    
    Handler is a thin routing layer - all logic is in orchestrator.
    """
    group_orchestrator = context.application.bot_data.get("group_orchestrator")
    
    if not group_orchestrator:
        logger.error("GroupOrchestrator not initialized in bot_data")
        return
    
    user_service = context.application.bot_data.get("user_service")
    bot_username = context.bot.username
    
    # Get user profile
    user_profile = await user_service.get_user_profile(
        user_id=user_id,
        username=update.effective_user.username or ""
    ) if user_service else None
    
    # Delegate EVERYTHING to orchestrator (moderation + response)
    await group_orchestrator.handle_message(
        update=update,
        context=context,
        user_message=user_message,
        user_id=user_id,
        user_profile=user_profile,
        bot_username=bot_username
    )


async def _handle_private_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_message: str,
    user_id: int
) -> None:
    """
    Handle private chat messages via AgentService.
    
    Uses ContentModerator (same as groups) for unified moderation.
    """
    agent = context.application.bot_data.get("agent")
    user_service = context.application.bot_data.get("user_service")
    content_moderator = context.application.bot_data.get("content_moderator")
    
    if not agent or not user_service:
        logger.error("Services not initialized in bot_data")
        return

    # Moderation check (unified ContentModerator)
    if content_moderator:
        mod_result = await content_moderator.check(user_message)
        
        if mod_result.is_flagged:
            await send_plain(
                update,
                "⚠️ Your message was flagged. Please use appropriate language."
            )
            return

    # Get user profile
    user_profile = await user_service.get_user_profile(
        user_id=user_id,
        username=update.effective_user.username or ""
    )
    
    # Process with agent
    response = await agent.process(
        user_message=user_message,
        user_id=user_id,
        user_profile=user_profile,
        user_service=user_service,
        chat_type="private"
    )
    
    # Send response
    await send_response(update, response)
    
    # Log interaction
    sh = context.application.bot_data.get("sh")
    if sh:
        try:
            log_interaction(
                sh,
                user_id=user_id,
                user_message=user_message,
                bot_response=response,
                screener_output="",
                intent_output="agent",
                entities_output=""
            )
        except Exception as log_error:
            logger.warning(f"Failed to log interaction: {log_error}")
