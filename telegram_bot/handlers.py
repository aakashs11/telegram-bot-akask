"""
Telegram bot message handlers.
Handles /start command and user messages with unified message sending.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from utils.gspread_logging import log_interaction
from telegram_bot.services.message_service import send_response, send_to_user, send_plain

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command with optional deep link parameters."""
    # Check if user came from a deep link (e.g., /notes button in group)
    args = context.args
    
    if args and args[0] == 'notes':
        # User clicked the button from a group to get notes
        welcome_message = (
            "👋 Hey! I'm ASK.ai - your study buddy!\n\n"
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
            "👋 Hey! I'm ASK.ai - your study buddy!\n\n"
            "I can help you find:\n"
            "📚 Notes, books & sample papers\n"
            "🎬 Video lessons\n\n"
            "Just tell me what you need!"
        )
    
    await send_response(update, welcome_message)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages - ONLY in private chats."""
    try:
        user_message = update.message.text
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type
        
        # Get services
        agent = context.application.bot_data.get("agent")
        user_service = context.application.bot_data.get("user_service")
        moderation_service = context.application.bot_data.get("moderation_service")
        
        if not agent or not user_service or not moderation_service:
            logger.error("Services not initialized in bot_data")
            return

        # --- GROUP CHAT LOGIC (Check before spam detection to save API calls) ---
        if chat_type in ['group', 'supergroup']:
            # Only respond if mentioned
            bot_username = context.bot.username
            if f"@{bot_username}" not in user_message:
                return  # Skip spam check for non-mentions
            
            # Remove mention from message for cleaner processing
            user_message = user_message.replace(f"@{bot_username}", "").strip()
            if not user_message:
                await send_plain(update, "Hi! How can I help you?")
                return

        # --- SPAM DETECTION & LOGGING (After filtering non-relevant messages) ---
        mod_result = await moderation_service.check_message(user_message)
        
        # Log to Google Sheets (if available)
        sh = context.application.bot_data.get("sh")
        action = "Allowed"
        
        if mod_result.is_flagged:
            action = "Deleted"
            try:
                await update.message.delete()
                
                # Send PRIVATE warning to user using unified service
                warning_text = (
                    "⚠️ *Safety Warning*\n\n"
                    "Your message was deleted because it violated our safety guidelines.\n"
                    "Please adhere to community standards."
                )
                await send_to_user(context, user_id, warning_text)
                    
            except Exception as e:
                logger.warning(f"Could not delete spam message: {e}")
                action = "Failed Delete"

        # Log the moderation event
        if sh:
            from utils.gspread_logging import log_moderation_event
            log_moderation_event(
                sh, 
                user_id, 
                update.effective_chat.id, 
                user_message, 
                mod_result.is_flagged, 
                mod_result.categories, 
                action
            )

        # Stop processing if flagged
        if mod_result.is_flagged:
            return

        # --- PRIVATE CHAT LOGIC ---
        # Get user profile (persistent!)
        user_profile = await user_service.get_user_profile(
            user_id=user_id,
            username=update.effective_user.username or ""
        )
        
        # Process message with agent
        response = await agent.process(
            user_message=user_message,
            user_id=user_id,
            user_profile=user_profile,
            user_service=user_service
        )
        
        # Send response (handles splitting automatically)
        await send_response(update, response)
        
        # Log interaction if Google Sheets is available
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
                
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await send_plain(update, "Sorry, I encountered an error. Please try again.")
