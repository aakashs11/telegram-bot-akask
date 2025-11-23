"""
User Service for managing persistent user profiles via Google Sheets.
Handles profile retrieval, updates, and automatic class progression.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Any
import gspread
from config.settings import get_sheet

logger = logging.getLogger(__name__)

class UserService:
    """
    Manages user profiles using Google Sheets as the backend.
    Implements simple caching to reduce API calls.
    """
    
    WORKSHEET_NAME = "UserProfiles"
    CACHE_TTL_SECONDS = 300  # 5 minutes cache
    
    def __init__(self):
        self._cache: Dict[int, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[int, float] = {}
        self._ensure_worksheet_exists()

    def _get_worksheet(self):
        """Get the UserProfiles worksheet"""
        sh = get_sheet()
        if not sh:
            logger.warning("Google Sheet not available")
            return None
        try:
            return sh.worksheet(self.WORKSHEET_NAME)
        except gspread.WorksheetNotFound:
            return self._create_worksheet(sh)
            
    def _create_worksheet(self, sh):
        """Create UserProfiles worksheet with headers"""
        try:
            ws = sh.add_worksheet(title=self.WORKSHEET_NAME, rows=1000, cols=10)
            headers = [
                "user_id", "username", "current_class", "preferred_subject", 
                "created_at", "last_updated", "class_updated_year"
            ]
            ws.append_row(headers)
            return ws
        except Exception as e:
            logger.error(f"Failed to create worksheet: {e}")
            return None

    def _ensure_worksheet_exists(self):
        """Initialize worksheet if needed"""
        self._get_worksheet()

    async def get_user_profile(self, user_id: int, username: str = "") -> Dict[str, Any]:
        """
        Get user profile, creating one if it doesn't exist.
        Also handles auto-progression check.
        """
        # Check cache first
        if user_id in self._cache:
            # Simple cache invalidation could go here
            return self._cache[user_id]

        ws = self._get_worksheet()
        if not ws:
            return {}

        try:
            # Find user row
            # Note: This is O(N) scan, acceptable for <1000 users. 
            # For scale, we'd fetch all and cache, or use a database.
            cell = ws.find(str(user_id), in_column=1)
            
            if cell:
                row_values = ws.row_values(cell.row)
                # Map columns to dict based on headers
                # Assuming fixed order for simplicity or we could read headers dynamically
                profile = {
                    "user_id": int(row_values[0]),
                    "username": row_values[1] if len(row_values) > 1 else "",
                    "current_class": int(row_values[2]) if len(row_values) > 2 and row_values[2].isdigit() else None,
                    "preferred_subject": row_values[3] if len(row_values) > 3 else None,
                    "class_updated_year": int(row_values[6]) if len(row_values) > 6 and row_values[6].isdigit() else 0
                }
                
                # Check for class progression
                updated_profile = self._check_auto_progression(profile)
                if updated_profile != profile:
                    await self.update_user_profile(user_id, updated_profile)
                    profile = updated_profile
                
                self._cache[user_id] = profile
                return profile
            else:
                # Create new profile
                new_profile = {
                    "user_id": user_id,
                    "username": username,
                    "current_class": None,
                    "preferred_subject": None,
                    "created_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "class_updated_year": datetime.now().year
                }
                
                row = [
                    str(user_id), username, "", "", 
                    new_profile["created_at"], new_profile["last_updated"], 
                    str(new_profile["class_updated_year"])
                ]
                ws.append_row(row)
                
                self._cache[user_id] = new_profile
                return new_profile

        except Exception as e:
            logger.error(f"Error fetching profile for {user_id}: {e}")
            return {}

    async def update_user_profile(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """Update specific fields in user profile"""
        ws = self._get_worksheet()
        if not ws:
            return False

        try:
            cell = ws.find(str(user_id), in_column=1)
            if not cell:
                return False # Should have been created in get_user_profile

            # Update cache
            if user_id in self._cache:
                self._cache[user_id].update(updates)

            # Update Sheet
            # Mapping fields to column indices (1-based)
            # 1:user_id, 2:username, 3:current_class, 4:preferred_subject, 
            # 5:created_at, 6:last_updated, 7:class_updated_year
            
            col_map = {
                "current_class": 3,
                "preferred_subject": 4,
                "last_updated": 6,
                "class_updated_year": 7
            }
            
            updates["last_updated"] = datetime.now().isoformat()
            
            for field, value in updates.items():
                if field in col_map:
                    ws.update_cell(cell.row, col_map[field], str(value))
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating profile for {user_id}: {e}")
            return False

    def _get_current_time(self) -> datetime:
        """Get current time (helper for testing)"""
        return datetime.now()

    def _check_auto_progression(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if student should be promoted to next class.
        Logic: If current date > June 1st AND last update was previous year.
        """
        current_class = profile.get("current_class")
        if not current_class:
            return profile

        last_update_year = profile.get("class_updated_year", 0)
        now = self._get_current_time()
        current_year = now.year
        
        # Promotion happens on June 1st
        promotion_date = datetime(current_year, 6, 1)
        
        # If we are past June 1st of current year, and haven't updated this year yet
        if now >= promotion_date and last_update_year < current_year:
            if current_class < 12:
                new_class = current_class + 1
                logger.info(f"🎓 Auto-promoting user {profile['user_id']} from {current_class} to {new_class}")
                
                # Return new profile dict (don't mutate original yet)
                new_profile = profile.copy()
                new_profile["current_class"] = new_class
                new_profile["class_updated_year"] = current_year
                return new_profile
        
        return profile
