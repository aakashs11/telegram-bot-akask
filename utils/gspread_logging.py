from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def log_interaction(sh, user_id, user_message, bot_response, screener_output="", intent_output="", entities_output=""):
    """
    Logs interaction details to a Google Sheet.
    """
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        row = [
            current_time,
            user_id,
            user_message,
            bot_response,
            screener_output,
            intent_output,
            entities_output
        ]
        worksheet = sh.sheet1
        worksheet.append_row(row)
        logger.info(f"Logged interaction for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to log interaction to Google Sheets: {e}")

def log_to_sheet(sh, user_id, username, input_message, screen_output, intent, entities, final_output):
    """
    Legacy function - kept for backward compatibility.
    """
    log_interaction(sh, user_id, input_message, final_output, screen_output, intent, entities)
