import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config.settings import TELEGRAM_BOT_TOKEN
from telegram_bot.handlers import start_command, handle_message
from telegram_bot.infrastructure.drive_note_repository import DriveNoteRepository
from telegram_bot.services import AgentService, UserService, ModerationService, DriveService, SyncService
from telegram_bot.services.note_service import NoteService
from telegram_bot.tools import NotesTool, VideosTool, ProfileTool, ListResourcesTool
from telegram_bot.commands.notes_command import NotesCommand
from telegram_bot.commands.sync_command import SyncCommand
from telegram_bot.commands.welcome_command import WelcomeCommand
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize Dependencies
# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# Initialize Services
drive_service = DriveService()
note_repository = DriveNoteRepository(drive_service)
note_service = NoteService(note_repository)
notes_command = NotesCommand(note_service)
user_service = UserService()
agent = AgentService()
moderation_service = ModerationService()

# Register Tools
agent.register_tool(NotesTool(note_service=note_service))
agent.register_tool(VideosTool())
agent.register_tool(ProfileTool())
agent.register_tool(ListResourcesTool(note_service=note_service))

logger.info(f"Agent initialized with {len(agent.tools)} tools")

# Create the Telegram bot Application
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Store services in bot_data for access in handlers
application.bot_data["agent"] = agent
application.bot_data["user_service"] = user_service
application.bot_data["moderation_service"] = moderation_service

# Initialize Sync Service
drive_sync_service = SyncService(drive_service)
sync_command = SyncCommand(drive_sync_service)

# Initialize Welcome Command
welcome_command = WelcomeCommand()

# Add command and message handlers
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("notes", notes_command.list_notes))
application.add_handler(CommandHandler("addnote", notes_command.add_note))
application.add_handler(CommandHandler("sync", sync_command.sync_drive))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_command.on_new_member))

# Background Sync Job
async def run_sync_job(context):
    """Runs the Drive sync in a separate thread to avoid blocking"""
    import asyncio
    loop = asyncio.get_running_loop()
    # Run synchronous sync_drive_to_index in a thread pool
    await loop.run_in_executor(None, drive_sync_service.sync_drive_to_index)

# Schedule sync every 5 minutes (300 seconds) to be safe on API quota
if application.job_queue:
    application.job_queue.run_repeating(run_sync_job, interval=300, first=10)
    logger.info("Scheduled Drive sync job every 300 seconds (5 min).")
