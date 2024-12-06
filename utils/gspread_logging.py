import pytz
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def log_to_sheet(sh, user_id, username, input_message, screen_output, intent, entities, final_output):
    """
    Logs interaction details to a Google Sheet.
    """
    try:
        ist = pytz.timezone("Asia/Kolkata")
        current_time = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

        row = [
            current_time,
            user_id,
            username,
            input_message,
            screen_output,
            intent,
            entities,
            final_output
        ]
        worksheet = sh.sheet1
        worksheet.append_row(row)
    except Exception as e:
        logger.error(f"Failed to log query details to Google Sheets: {e}")
