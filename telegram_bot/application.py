import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config.settings import TOKEN
from telegram_bot.handlers import start, handle_message

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # You can change this to INFO or ERROR in production
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create the Telegram bot Application
application = Application.builder().token(TOKEN).build()

# Add command and message handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
