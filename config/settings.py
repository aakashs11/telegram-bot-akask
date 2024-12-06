import os
import logging
import json

from dotenv import load_dotenv
import google.auth
import gspread

# Load environment variables from .env file
load_dotenv()
    
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NGROK_URL = os.getenv("NGROK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
CLOUD_RUN_URL = os.getenv("CLOUD_RUN_URL")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in the environment variables.")

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # or logging.INFO based on your preference
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

logger.debug(
    f"Telegram Token: {TELEGRAM_BOT_TOKEN}, NGROK_URL: {NGROK_URL}, OPENAI_API_KEY: {OPENAI_API_KEY}"
)

# Google authentication and Sheets access
credentials, project = google.auth.default()
logger.debug(f"Service Account Email: {credentials.service_account_email}")

gc = gspread.authorize(credentials)
sh = gc.open_by_key("1-1Y4O4RAa-XgtAcGB_tEzXE3dta8pYxCgzj5o9FRqM0")
logger.info("Spreadsheet opened successfully.")

# Constants for YouTube API (if needed)
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
