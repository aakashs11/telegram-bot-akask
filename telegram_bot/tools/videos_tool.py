"""
Video search tool.
Searches YouTube channel for educational videos.
"""

from typing import Dict, Any, Optional
from telegram_bot.tools.base import BaseTool
from functions.videos import get_videos as search_videos


class VideosTool(BaseTool):
    """Tool for searching educational videos on YouTube"""
    
    @property
    def name(self) -> str:
        return "search_videos"
    
    @property
    def description(self) -> str:
        return "Search for educational videos on a specific topic from the YouTube channel"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic or keyword to search for (e.g., 'Python basics', 'data structures')"
                }
            },
            "required": ["topic"]
        }
    
    async def execute(
        self,
        topic: str,
        user_profile: Optional[Dict] = None,
        **kwargs  # Accept additional args
    ) -> str:
        """
        Execute video search.
        
        Args:
            topic: Search topic/keyword
            **kwargs: Additional arguments (ignored)
            
        Returns:
            Formatted list of video results
        """
        query = {"topic": topic}
        result = await search_videos(query)
        return result
