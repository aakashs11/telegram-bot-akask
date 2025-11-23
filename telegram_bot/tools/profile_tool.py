"""
User profile management tool.
Updates user's class and subject preferences.
"""

from typing import Dict, Any, Optional
from telegram_bot.tools.base import BaseTool


class ProfileTool(BaseTool):
    """Tool for updating user profile preferences"""
    
    @property
    def name(self) -> str:
        return "update_user_profile"
    
    @property
    def description(self) -> str:
        return "Update user's class or subject preference in their profile"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "class_number": {
                    "type": "integer",
                    "description": "New class number (10, 11, or 12)",
                    "enum": [10, 11, 12]
                },
                "subject": {
                    "type": "string",
                    "description": "New preferred subject",
                    "enum": ["AI", "IT", "CS", "IP"]
                }
            },
            "required": []  # Both optional
        }
    
    async def execute(
        self,
        class_number: Optional[int] = None,
        subject: Optional[str] = None,
        user_id: Optional[int] = None,
        user_service: Optional[Any] = None,
        **kwargs
    ) -> str:
        """
        Execute profile update.
        
        Args:
            class_number: New class (optional)
            subject: New subject (optional)
            user_id: User ID for update
            user_service: Service to perform update
            **kwargs: Additional arguments (ignored)
            
        Returns:
            Confirmation message
        """
        if not user_service or not user_id:
            return "Unable to update profile at this time."
        
        updates = {}
        if class_number:
            updates['current_class'] = class_number
        if subject:
            updates['preferred_subject'] = subject
        
        if not updates:
            return "Please specify what you'd like to update (class or subject)."
        
        # Update profile using UserService
        if user_service:
            success = await user_service.update_user_profile(user_id, updates)
            if not success:
                return "Failed to save profile updates. Please try again."
        
        messages = []
        if class_number:
            messages.append(f"✅ Updated class to {class_number}")
        if subject:
            messages.append(f"✅ Updated subject to {subject}")
        
        return "\n".join(messages)
