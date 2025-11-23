"""
Model configuration for different use cases.
Allows easy switching between GPT-4o, GPT-4o-mini, and custom settings.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelConfig:
    """Configuration for OpenAI models"""
    name: str = "gpt-4o"
    temperature: float = 0.2
    max_tokens: int = 300
    top_p: Optional[float] = None
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0


# Predefined configurations for different use cases
CONFIGS = {
    "assistant": ModelConfig(
        name=os.getenv("AGENT_MODEL", "gpt-4o"),
        temperature=float(os.getenv("AGENT_TEMPERATURE", "0.3")),
        max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "500"))
    ),
    "moderation": ModelConfig(
        name=os.getenv("MODERATION_MODEL", "gpt-4o-mini"),
        temperature=float(os.getenv("MODERATION_TEMPERATURE", "0.0")),
        max_tokens=int(os.getenv("MODERATION_MAX_TOKENS", "100"))
    ),
    "doubts": ModelConfig(
        name=os.getenv("DOUBTS_MODEL", "gpt-4o"),
        temperature=float(os.getenv("DOUBTS_TEMPERATURE", "0.5")),
        max_tokens=int(os.getenv("DOUBTS_MAX_TOKENS", "800"))
    )
}


def get_model_config(use_case: str = "assistant") -> ModelConfig:
    """
    Get model configuration for specific use case.
    
    Args:
        use_case: One of 'assistant', 'moderation', 'doubts'
        
    Returns:
        ModelConfig instance
    """
    return CONFIGS.get(use_case, CONFIGS["assistant"])
