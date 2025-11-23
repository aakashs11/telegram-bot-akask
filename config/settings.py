import os
import logging
from typing import Optional

from dotenv import load_dotenv


# Load environment variables from .env file (local dev convenience)
load_dotenv()


# Core configuration via environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NGROK_URL = os.getenv("NGROK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
CLOUD_RUN_URL = os.getenv("CLOUD_RUN_URL")
# Google Sheets
SHEET_ID = os.getenv("SHEET_ID", "1-1Y4O4RAa-XgtAcGB_tEzXE3dta8pYxCgzj5o9FRqM0")

# Google Drive
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID", "")  # Root folder to scan
DRIVE_CONFIG_FOLDER_NAME = os.getenv("DRIVE_CONFIG_FOLDER_NAME", "bot_config")  # Folder for index.json
PROVIDER = os.getenv("PROVIDER", "openai")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "300"))
RETRIEVER_STORE_PATH = os.getenv("RETRIEVER_STORE_PATH", "retriever_store")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
AGENT_SQLITE_PATH = os.getenv("AGENT_SQLITE_PATH", "agent_memory.db")
CREDENTIALS_FILE = "service_account.json"

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in the environment variables.")


# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Lazily initialized Google Sheet handle to avoid heavy side effects at import time
_sheet_handle = None  # type: ignore[var-annotated]


def get_sheet():
    """
    Lazily acquire and cache a Google Sheet handle using application default credentials.
    Returns None if credentials are not available or opening fails, to keep app responsive.
    """
    global _sheet_handle
    if _sheet_handle is not None:
        return _sheet_handle

    try:
        import google.auth
        import gspread

        # Check for service_account.json first (Local Dev)
        service_account_path = "service_account.json"
        if os.path.exists(service_account_path):
            logger.info(f"Found {service_account_path}, using for credentials.")
            gc = gspread.service_account(filename=service_account_path)
        else:
            # Fallback to Application Default Credentials (Production/Cloud Run)
            logger.info("No service_account.json found, using Application Default Credentials.")
            credentials, _ = google.auth.default()
            gc = gspread.authorize(credentials)
            
        _sheet_handle = gc.open_by_key(SHEET_ID)
        logger.info("Google Sheet opened successfully.")
    except Exception as exc:
        logger.warning(f"Google Sheet not initialized: {exc}")
        _sheet_handle = None
    return _sheet_handle


# Constants for YouTube API (if needed)
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
