"""
List available resources tool.
Shows what study materials are available for a class.
"""

from typing import Dict, Any, Optional
from collections import defaultdict
from telegram_bot.tools.base import BaseTool


class ListResourcesTool(BaseTool):
    """Tool for listing available study materials"""
    
    def __init__(self, note_service=None):
        """
        Args:
            note_service: Injected NoteService instance
        """
        self.note_service = note_service
    
    @property
    def name(self) -> str:
        return "list_available_resources"
    
    @property
    def description(self) -> str:
        return "Show what study materials are available for a specific class"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "class_number": {
                    "type": "integer",
                    "description": "Class number to show resources for (10, 11, or 12)",
                    "enum": [10, 11, 12]
                }
            },
            "required": []
        }
    
    async def execute(
        self,
        class_number: Optional[int] = None,
        user_profile: Optional[Dict] = None,
        **kwargs  # Accept additional args
    ) -> str:
        """
        List available resources.
        
        Args:
            class_number: Optional class (uses profile default if not provided)
            user_profile: User profile for defaults
            **kwargs: Additional arguments (ignored)
            
        Returns:
            Formatted list of available resources
        """
        # Use profile default if not provided
        if not class_number and user_profile:
            class_number = user_profile.get('current_class')
        
        if not class_number:
            return "Please specify which class (10, 11, or 12)."
        
        if not self.note_service:
            return "ERROR: Service not available."
        
        # Fetch all notes from Sheet for this class
        notes = await self.note_service.get_notes(class_num=class_number)
        
        if not notes:
            return f"No resources found for Class {class_number}."
        
        # Group by subject and resource type
        # Note tags format: [class, subject, type]
        grouped = defaultdict(lambda: defaultdict(int))
        
        for note in notes:
            if len(note.tags) >= 3:
                subject = note.tags[1]
                resource_type = note.tags[2]
                grouped[subject][resource_type] += 1
        
        # Build response
        response = [f"📚 **Available for Class {class_number}:**\n"]
        
        for subject in sorted(grouped.keys()):
            response.append(f"\n**{subject}:**")
            for resource_type, count in sorted(grouped[subject].items()):
                response.append(f"  • {resource_type}: {count} items")
        
        return "\n".join(response)
