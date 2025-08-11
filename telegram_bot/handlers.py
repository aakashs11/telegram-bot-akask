import logging
from telegram import Update
from telegram.ext import ContextTypes

from utils.intent import classify_intent
from utils.gspread_logging import log_interaction

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    welcome_message = (
        "👋 Welcome to ASK.ai!\n\n"
        "I can help you find:\n"
        "📚 Notes, books, and study materials\n"
        "🎥 Educational videos\n\n"
        "Just ask me what you need!"
    )
    await update.message.reply_text(welcome_message)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages."""
    try:
        user_message = update.message.text
        user_id = update.effective_user.id
        
        # Get Google Sheets client from bot_data (set in main.py)
        sh = context.application.bot_data.get("sh")
        
        # Classify intent and get response
        result = await classify_intent(user_message, user_id, sh)
        response = result.get("final_output", "Sorry, I couldn't process that.")
        
        # Send response (no parse_mode to avoid markdown issues)
        await update.message.reply_text(
            response, 
            disable_web_page_preview=True
        )
        
        # Log interaction if Google Sheets is available
        if sh:
            try:
                log_interaction(
                    sh,
                    user_id=user_id,
                    user_message=user_message,
                    bot_response=response,
                    screener_output=result.get("output_screener", ""),
                    intent_output=result.get("output_intent", ""),
                    entities_output=result.get("output_entitites", "")
                )
            except Exception as log_error:
                logger.warning(f"Failed to log interaction: {log_error}")
                
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await update.message.reply_text("Sorry, I encountered an error. Please try again.")

