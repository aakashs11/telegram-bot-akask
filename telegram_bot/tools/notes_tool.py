"""
Notes retrieval tool.
Fetches study materials from the Google Sheet via NoteService.
Provides folder links when available, falls back to file listing.
"""

from typing import Dict, Any, Optional
from telegram_bot.tools.base import BaseTool


class NotesTool(BaseTool):
    """Tool for retrieving study notes, books, syllabus, and sample papers"""
    
    def __init__(self, note_service=None):
        """        Args:
            note_service: Injected NoteService instance
        """
        self.note_service = note_service
    
    @property
    def name(self) -> str:
        return "get_notes"
    
    @property
    def description(self) -> str:
        return "Retrieve study materials including notes, books, syllabus, or sample papers for a specific class and subject"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "class_number": {
                    "type": "integer",
                    "description": "Class number (10, 11, or 12)",
                    "enum": [10, 11, 12]
                },
                "subject": {
                    "type": "string",
                    "description": "Subject code",
                    "enum": ["AI", "IT", "CS", "IP"]
                },
                "resource_type": {
                    "type": "string",
                    "description": "Type of resource to retrieve",
                    "enum": ["Notes", "Books", "Syllabus", "Sample Question Papers"]
                },
                "topic": {
                    "type": "string",
                    "description": "Optional specific topic (e.g., 'NLP', 'Computer Vision', 'Unit 1')"
                }
            },
            "required": []  # All optional - will use user profile defaults
        }
    
    async def execute(
        self,
        class_number: Optional[int] = None,
        subject: Optional[str] = None,
        resource_type: Optional[str] = None,
        topic: Optional[str] = None,
        user_profile: Optional[Dict] = None,
        **kwargs  # Accept additional args like user_id
    ) -> str:
        """
        Execute notes retrieval.
        
        Args:
            class_number: Optional class (uses user profile if not provided)
            subject: Optional subject (uses user profile if not provided)
            resource_type: Type of resource (defaults to "Notes")
            topic: Optional specific topic/subfolder
            user_profile: User profile dict for defaults
            
        Returns:
            Formatted response with folder link or file list
        """
        # Use profile defaults if not provided
        if user_profile:
            class_number = class_number or user_profile.get('current_class')
            subject = subject or user_profile.get('preferred_subject')
        
        resource_type = resource_type or "Notes"
        
        # Validate we have required info
        if not class_number or not subject:
            return (
                "MISSING_PARAMS: I need both class and subject to fetch notes. "
                "Please ask the user: 'Which class (10-12) and subject (AI/CS/IP/IT) are you looking for?'"
            )
        
        # Check service availability
        if not self.note_service:
            return "ERROR: Note service not available. Please contact admin."
        
        # 1. Try to get folder link (adaptive: with or without topic)
        folder_url = await self.note_service.get_folder_link(
            class_num=class_number,
            subject=subject,
            resource_type=resource_type,
            topic=topic
        )
        
        if folder_url:
            # Success! Return folder link
            topic_text = f" ({topic})" if topic else ""
            return (
                f"📚 **{resource_type} for Class {class_number} {subject}{topic_text}:**\n\n"
                f"🔗 [Open Folder in Google Drive]({folder_url})\n\n"
                f"💡 Tip: You can browse all files in the folder and download what you need!"
            )
        
        # 2. Fallback: List individual files (e.g., if topic-specific folder doesn't exist)
        notes = await self.note_service.get_notes(
            class_num=class_number,
            subject=subject,
            resource_type=resource_type,
            topic=topic
        )
        
        if not notes:
            suggestion = f" for topic '{topic}'" if topic else ""
            return f"📚 No {resource_type} found for Class {class_number} {subject}{suggestion}. Try a different search or contact admin."
        
        # Format file list response
        topic_text = f" - {topic}" if topic else ""
        response = f"📚 **{resource_type} for Class {class_number} {subject}{topic_text}:**\n\n"
        
        for note in notes[:5]:  # Limit to 5 files when listing
            response += f"📄 [{note.title}]({note.url})\n"
        
        if len(notes) > 5:
            response += f"\n📦 ...and {len(notes) - 5} more files available!"
        
        return response
