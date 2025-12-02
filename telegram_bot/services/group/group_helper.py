"""
Group Helper Service.

Extracts context from group names and handles quote-replies.
Helps the bot understand what class/subject a group is for
without requiring users to specify.
"""

import re
import logging
from typing import Dict, Optional
from telegram import Message

logger = logging.getLogger(__name__)


class GroupHelper:
    """
    Helper for extracting context from group interactions.
    
    Responsibilities:
    - Parse group names to extract class/subject (e.g., "Class 12 AI Study")
    - Extract text from quote-replies
    - Determine if bot has enough context to respond
    """
    
    # Known subjects in the system
    SUBJECTS = ["AI", "CS", "IP", "IT"]
    
    # Valid class numbers
    CLASSES = [10, 11, 12]
    
    # Regex patterns for flexible parsing
    # Matches: "Class 12", "class12", "Class-12", "class 12th"
    CLASS_PATTERN = re.compile(
        r'class[\s\-_]?(\d{1,2})(?:th)?',
        re.IGNORECASE
    )
    
    def extract_from_group_name(self, group_title: str) -> Dict[str, Optional[any]]:
        """
        Extract class and subject from a group name.
        
        Args:
            group_title: The Telegram group title/name
            
        Returns:
            Dict with 'class' (int or None) and 'subject' (str or None)
            
        Examples:
            "Class 12 AI Study Group" -> {"class": 12, "subject": "AI"}
            "CS Class 11 Students" -> {"class": 11, "subject": "CS"}
            "Study Group" -> {"class": None, "subject": None}
        """
        result = {"class": None, "subject": None}
        
        if not group_title:
            return result
        
        title_upper = group_title.upper()
        
        # Extract class number
        class_match = self.CLASS_PATTERN.search(group_title)
        if class_match:
            class_num = int(class_match.group(1))
            if class_num in self.CLASSES:
                result["class"] = class_num
        
        # Extract subject
        for subject in self.SUBJECTS:
            if subject in title_upper:
                result["subject"] = subject
                break
        
        if result["class"] or result["subject"]:
            logger.info(f"Extracted from group name '{group_title}': {result}")
        
        return result
    
    def extract_quote_reply(self, message: Message) -> Optional[str]:
        """
        Extract text from a replied-to message.
        
        Args:
            message: Telegram Message object
            
        Returns:
            Text of the replied message, or None if no reply
        """
        if message.reply_to_message and message.reply_to_message.text:
            replied_text = message.reply_to_message.text
            logger.debug(f"Quote-reply extracted: '{replied_text[:50]}...'")
            return replied_text
        return None
    
    def build_context_message(
        self,
        user_message: str,
        replied_text: Optional[str] = None,
        group_context: Optional[Dict] = None
    ) -> str:
        """
        Build a context-enriched message for the agent.
        
        Args:
            user_message: The user's actual message
            replied_text: Text from quoted reply (if any)
            group_context: Class/subject from group name (if any)
            
        Returns:
            Enriched message with context prepended
        """
        parts = []
        
        # Add group context if available
        if group_context:
            ctx_parts = []
            if group_context.get("class"):
                ctx_parts.append(f"Class {group_context['class']}")
            if group_context.get("subject"):
                ctx_parts.append(group_context["subject"])
            if ctx_parts:
                parts.append(f"[Group context: {' '.join(ctx_parts)}]")
        
        # Add replied message if available
        if replied_text:
            parts.append(f"[Replying to: {replied_text}]")
        
        # Add user's message
        if user_message:
            parts.append(user_message)
        
        return "\n".join(parts) if parts else ""
    
    def has_sufficient_context(
        self,
        user_message: str,
        group_context: Optional[Dict] = None,
        user_profile: Optional[Dict] = None
    ) -> bool:
        """
        Check if we have enough context to respond without asking questions.
        
        For notes/papers requests, we need at least class OR subject
        from group name or user profile.
        
        Args:
            user_message: The user's message
            group_context: Context from group name
            user_profile: User's saved profile
            
        Returns:
            True if we can respond without asking for more info
        """
        # Check if message is a resource request
        resource_keywords = ["notes", "paper", "book", "syllabus", "material", "pdf"]
        is_resource_request = any(kw in user_message.lower() for kw in resource_keywords)
        
        if not is_resource_request:
            # Non-resource requests don't need class/subject
            return True
        
        # For resource requests, check if we have context
        has_class = (
            (group_context and group_context.get("class")) or
            (user_profile and user_profile.get("current_class"))
        )
        has_subject = (
            (group_context and group_context.get("subject")) or
            (user_profile and user_profile.get("preferred_subject"))
        )
        
        return has_class or has_subject

