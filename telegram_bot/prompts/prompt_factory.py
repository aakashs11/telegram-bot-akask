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
    def build_system_prompt(cls, user_profile: Optional[Dict] = None) -> str:
        """
        Build the main agent system prompt with optional user profile context.
        
        Args:
            user_profile: Optional user profile dict with 'current_class' and 'preferred_subject'
            
        Returns:
            Complete system prompt string
        """
        # Load base prompt from file
        base_prompt = cls._load_prompt_file('agent_system.md')
        
        # If profile provided, inject profile section
        if user_profile:
            class_num = user_profile.get('current_class', 'None')
            subject = user_profile.get('preferred_subject', '')
            
            # Load profile template
            profile_template = cls._load_prompt_file('profile_section.md')
            profile_section = profile_template.format(
                class_num=class_num,
                subject=subject
            )
            
            # Insert profile section after the intro line
            base_prompt = base_prompt.replace(
                "You're helpful, conversational, and understand natural student language.",
                f"You're helpful, conversational, and understand natural student language.\n\n{profile_section}"
            )
        
        return base_prompt
    
    @classmethod
    def get_spam_detection_prompt(cls) -> str:
        """Get the spam detection system prompt from file"""
        return cls._load_prompt_file('spam_detection.md')
