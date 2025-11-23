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
        try:
            worksheet = sh.worksheet("Logs")
        except:
            # Create Logs worksheet if it doesn't exist
            worksheet = sh.add_worksheet(title="Logs", rows=1000, cols=7)
            worksheet.append_row([
                "Timestamp", "User ID", "User Message", "Bot Response", 
                "Screener", "Intent", "Entities"
            ])
            
        worksheet.append_row(row)
        logger.info(f"Logged interaction for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to log interaction to Google Sheets: {e}")

def log_moderation_event(sh, user_id, group_id, message_text, is_spam, categories, action):
    """
    Logs moderation events to 'ModerationLogs' sheet.
    """
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snippet = message_text[:50] + "..." if len(message_text) > 50 else message_text
        
        row = [
            current_time,
            str(user_id),
            str(group_id),
            snippet,
            "TRUE" if is_spam else "FALSE",
            ", ".join(categories),
            action
        ]
        
        try:
            worksheet = sh.worksheet("ModerationLogs")
        except:
            # Create ModerationLogs worksheet
            worksheet = sh.add_worksheet(title="ModerationLogs", rows=1000, cols=7)
            worksheet.append_row([
                "Timestamp", "User ID", "Group ID", "Message Snippet", 
                "Is Spam", "Categories", "Action Taken"
            ])
            
        worksheet.append_row(row)
        logger.info(f"Logged moderation event for user {user_id}")
        
    except Exception as e:
        logger.error(f"Failed to log moderation event: {e}")

def log_drive_change(sh, change_type, filename, file_id, metadata):
    """
    Logs Drive sync changes to 'DriveSyncLogs' sheet.
    """
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        row = [
            current_time,
            change_type,  # "ADDED", "REMOVED", "UPDATED"
            filename,
            file_id,
            str(metadata)
        ]
        
        try:
            worksheet = sh.worksheet("DriveSyncLogs")
        except:
            # Create DriveSyncLogs worksheet
            worksheet = sh.add_worksheet(title="DriveSyncLogs", rows=1000, cols=5)
            worksheet.append_row([
                "Timestamp", "Change Type", "Filename", "File ID", "Metadata"
            ])
            
        worksheet.append_row(row)
        logger.info(f"Logged Drive change: {change_type} - {filename}")
        
    except Exception as e:
        logger.error(f"Failed to log Drive change: {e}")

    except Exception as e:
        logger.error(f"Failed to log Drive change: {e}")

def log_drive_changes_batch(sh, changes: list):
    """
    Logs multiple Drive sync changes to 'DriveSyncLogs' sheet in one batch.
    Args:
        sh: Google Sheet object
        changes: List of dicts with keys: change_type, filename, file_id, metadata
    """
    if not changes:
        return

    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = []
        
        for change in changes:
            rows.append([
                current_time,
                change['change_type'],
                change['filename'],
                change['file_id'],
                str(change['metadata'])
            ])
        
        try:
            worksheet = sh.worksheet("DriveSyncLogs")
        except:
            try:
                # Create DriveSyncLogs worksheet
                worksheet = sh.add_worksheet(title="DriveSyncLogs", rows=1000, cols=5)
                worksheet.append_row([
                    "Timestamp", "Change Type", "Filename", "File ID", "Metadata"
                ])
            except Exception as create_error:
                # If creation fails (e.g. race condition), try fetching again
                logger.warning(f"Sheet creation failed (might exist): {create_error}")
                worksheet = sh.worksheet("DriveSyncLogs")
            
        worksheet.append_rows(rows)
        logger.info(f"Logged {len(rows)} Drive changes in batch")
        
    except Exception as e:
        logger.error(f"Failed to log batch Drive changes: {e}")

def log_to_sheet(sh, user_id, username, input_message, screen_output, intent, entities, final_output):
    """
    Legacy function - kept for backward compatibility.
    """
    log_interaction(sh, user_id, input_message, final_output, screen_output, intent, entities)
