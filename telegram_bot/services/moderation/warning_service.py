"""
Warning Service.

Tracks user warnings and manages automatic bans.
Uses Google Sheets as storage for persistence across restarts.

Warning System:
- 1st violation: Warning sent to user
- 2nd violation: Warning + final notice
- 3rd violation: Auto-ban from group
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

import gspread
from config.settings import get_sheet

logger = logging.getLogger(__name__)


@dataclass
class WarningResult:
    """
    Result of adding a warning.
    
    Attributes:
        warning_count: Total warnings for this user in this chat
        should_ban: Whether user should be banned (exceeded threshold)
        message: Warning message to send to user
    """
    warning_count: int
    should_ban: bool
    message: str


class WarningService:
    """
    Manages user warnings and automatic bans.
    
    Storage: Google Sheets "Warnings" worksheet
    Columns: user_id, chat_id, username, warning_count, last_reason, last_warning, banned
    
    Ban threshold: 2 warnings (configurable)
    """
    
    WORKSHEET_NAME = "Warnings"
    BAN_THRESHOLD = 2  # Ban after 2 warnings
    
    def __init__(self):
        """Initialize the warning service."""
        self._cache: Dict[str, Dict[str, Any]] = {}  # key: f"{user_id}:{chat_id}"
        self._ensure_worksheet_exists()
        logger.info("WarningService initialized")
    
    def _get_worksheet(self) -> Optional[gspread.Worksheet]:
        """Get the Warnings worksheet."""
        sh = get_sheet()
        if not sh:
            logger.warning("Google Sheet not available for warnings")
            return None
        try:
            return sh.worksheet(self.WORKSHEET_NAME)
        except gspread.WorksheetNotFound:
            return self._create_worksheet(sh)
    
    def _create_worksheet(self, sh) -> Optional[gspread.Worksheet]:
        """Create Warnings worksheet with headers."""
        try:
            ws = sh.add_worksheet(title=self.WORKSHEET_NAME, rows=1000, cols=10)
            headers = [
                "user_id", "chat_id", "username", "warning_count",
                "last_reason", "last_warning", "banned"
            ]
            ws.append_row(headers)
            logger.info("Created Warnings worksheet")
            return ws
        except Exception as e:
            logger.error(f"Failed to create Warnings worksheet: {e}")
            return None
    
    def _ensure_worksheet_exists(self):
        """Initialize worksheet if needed."""
        self._get_worksheet()
    
    def _get_cache_key(self, user_id: int, chat_id: int) -> str:
        """Generate cache key for user+chat combination."""
        return f"{user_id}:{chat_id}"
    
    async def get_warning_count(self, user_id: int, chat_id: int) -> int:
        """
        Get current warning count for a user in a chat.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        Returns:
            Number of warnings (0 if none)
        """
        cache_key = self._get_cache_key(user_id, chat_id)
        
        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key].get("warning_count", 0)
        
        ws = self._get_worksheet()
        if not ws:
            return 0
        
        try:
            # Find user row
            cell = ws.find(str(user_id), in_column=1)
            if cell:
                row = ws.row_values(cell.row)
                # Check if chat_id matches (column 2)
                if len(row) > 1 and row[1] == str(chat_id):
                    count = int(row[3]) if len(row) > 3 and row[3].isdigit() else 0
                    self._cache[cache_key] = {"warning_count": count}
                    return count
            return 0
        except Exception as e:
            logger.error(f"Error getting warning count: {e}")
            return 0
    
    async def add_warning(
        self,
        user_id: int,
        chat_id: int,
        username: str = "",
        reason: str = "content_violation"
    ) -> WarningResult:
        """
        Add a warning for a user.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            username: Username for logging
            reason: Reason for warning
            
        Returns:
            WarningResult with count, ban status, and message
        """
        ws = self._get_worksheet()
        cache_key = self._get_cache_key(user_id, chat_id)
        current_count = await self.get_warning_count(user_id, chat_id)
        new_count = current_count + 1
        should_ban = new_count >= self.BAN_THRESHOLD
        
        # Update storage
        if ws:
            try:
                cell = ws.find(str(user_id), in_column=1)
                now = datetime.now().isoformat()
                
                if cell:
                    # Check if same chat_id
                    row = ws.row_values(cell.row)
                    if len(row) > 1 and row[1] == str(chat_id):
                        # Update existing row
                        ws.update_cell(cell.row, 4, str(new_count))  # warning_count
                        ws.update_cell(cell.row, 5, reason)  # last_reason
                        ws.update_cell(cell.row, 6, now)  # last_warning
                        if should_ban:
                            ws.update_cell(cell.row, 7, "TRUE")  # banned
                    else:
                        # Different chat, create new row
                        ws.append_row([
                            str(user_id), str(chat_id), username,
                            str(new_count), reason, now,
                            "TRUE" if should_ban else "FALSE"
                        ])
                else:
                    # Create new row
                    ws.append_row([
                        str(user_id), str(chat_id), username,
                        str(new_count), reason, now,
                        "TRUE" if should_ban else "FALSE"
                    ])
                    
            except Exception as e:
                logger.error(f"Error updating warning: {e}")
        
        # Update cache
        self._cache[cache_key] = {"warning_count": new_count}
        
        # Generate warning message
        # Note: BAN_THRESHOLD = 2 means ban on 2nd violation
        if should_ban:
            message = (
                "🚫 *BANNED*\n\n"
                "You have been *permanently removed* from the group.\n\n"
                "Reason: Repeated violations of community guidelines "
                "(spam, abuse, or inappropriate content).\n\n"
                "This was your 2nd violation. This action is logged."
            )
        else:
            # First and only warning before ban
            message = (
                "⚠️ *WARNING - FIRST AND FINAL*\n\n"
                "Your message was *deleted* for containing inappropriate content "
                "(spam, abuse, or policy violation).\n\n"
                "🚨 *You are now being tracked:*\n"
                "• This warning is logged permanently\n"
                "• Your user ID is recorded\n"
                "• *NEXT violation = PERMANENT BAN*\n\n"
                "This is your only warning. Follow community guidelines."
            )
        
        logger.info(f"Warning added: user={user_id}, chat={chat_id}, count={new_count}, ban={should_ban}")
        
        return WarningResult(
            warning_count=new_count,
            should_ban=should_ban,
            message=message
        )
    
    async def execute_ban(self, bot, user_id: int, chat_id: int) -> bool:
        """
        Execute a ban on a user.
        
        Args:
            bot: Telegram bot instance
            user_id: User to ban
            chat_id: Chat to ban from
            
        Returns:
            True if ban was successful
        """
        try:
            await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            logger.info(f"Banned user {user_id} from chat {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to ban user {user_id}: {e}")
            return False
    
    async def is_banned(self, user_id: int, chat_id: int) -> bool:
        """Check if a user is banned in a chat."""
        ws = self._get_worksheet()
        if not ws:
            return False
        
        try:
            cell = ws.find(str(user_id), in_column=1)
            if cell:
                row = ws.row_values(cell.row)
                if len(row) > 6 and row[1] == str(chat_id):
                    return row[6].upper() == "TRUE"
            return False
        except Exception as e:
            logger.error(f"Error checking ban status: {e}")
            return False

