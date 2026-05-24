"""
Prompt Factory for ASK.ai Bot
Loads prompts from .md files for easy editing without touching code.
Uses caching to avoid repeated file I/O.
"""

from typing import Dict, Optional
from pathlib import Path
from functools import lru_cache


class PromptFactory:
    """Factory for building prompts dynamically from .md files"""
    
    # Directory containing prompt files
    PROMPTS_DIR = Path(__file__).parent
    
    @staticmethod
    @lru_cache(maxsize=10)
    def _load_prompt_file(filename: str) -> str:
        """
        Load a prompt from a .md file with caching.
        
        Args:
            filename: Name of the .md file (without path)
            
        Returns:
            Content of the file as string
        """
        file_path = PromptFactory.PROMPTS_DIR / filename
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Prompt file not found: {file_path}\n"
                f"Make sure {filename} exists in {PromptFactory.PROMPTS_DIR}"
            )
    
    @classmethod
    def build_system_prompt(cls, user_profile: Optional[Dict] = None, is_admin: bool = False) -> str:
        """
        Build the main agent system prompt with optional user profile context.
        
        Args:
            user_profile: Optional user profile dict with 'current_class' and 'preferred_subject'
            is_admin: If True, user has admin privileges (can access all notes)
            
        Returns:
            Complete system prompt string
        """
        # Load base prompt from file
        base_prompt = cls._load_prompt_file('agent_system.md')

        # Build inserts for the intro line
        anchor = "You're helpful, conversational, and understand natural student language."
        inserts = []

        if is_admin:
            inserts.append(
                "\n\n🔐 **ADMIN MODE**: This user is an admin. They can request notes for "
                "ANY class (10, 11, 12) and subject (AI, CS, IP, IT). Use list_available_resources "
                "without class to show all, or get_notes with any class/subject they specify."
            )

        # Inject profile section based on how much is known.
        # Every new user gets an auto-created profile with both fields as None,
        # so a truthy dict alone is not sufficient — check the values.
        class_num = user_profile.get('current_class') if user_profile else None
        subject = user_profile.get('preferred_subject') if user_profile else None

        if class_num and subject:
            # Full profile — use defaults, do not ask
            profile_template = cls._load_prompt_file('profile_section.md')
            profile_section = profile_template.format(
                class_num=class_num,
                subject=subject,
            )
            inserts.append(f"\n\n{profile_section}")
        elif class_num or subject:
            # Partial profile — only ask for the missing field
            missing = "subject" if class_num else "class"
            profile_template = cls._load_prompt_file('profile_section_partial.md')
            profile_section = profile_template.format(
                class_num=class_num or "not set yet",
                subject=subject or "not set yet",
                missing=missing,
            )
            inserts.append(f"\n\n{profile_section}")

        if inserts:
            base_prompt = base_prompt.replace(
                anchor,
                anchor + "".join(inserts)
            )
        
        return base_prompt
    
    @classmethod
    def get_spam_detection_prompt(cls) -> str:
        """Get the spam detection system prompt from file"""
        return cls._load_prompt_file('spam_detection.md')
    
    @classmethod
    def get_content_moderation_prompt(cls) -> str:
        """Get the content moderation prompt from file"""
        return cls._load_prompt_file('content_moderation.md')
