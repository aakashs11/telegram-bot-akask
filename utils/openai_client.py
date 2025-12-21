"""
OpenAI client utilities for the Responses API.

This module provides a singleton OpenAI client instance for use across the application.
"""

from openai import OpenAI

# Lazy initialization of the OpenAI client
_client = None


def get_client() -> OpenAI:
    """
    Get or create OpenAI client instance.
    
    Returns:
        OpenAI: Configured OpenAI client instance
        
    Raises:
        ValueError: If OPENAI_API_KEY is not configured
    """
    global _client
    if _client is None:
        from config.settings import OPENAI_API_KEY
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured in settings")
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client
