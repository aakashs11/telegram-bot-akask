"""
Group services package.

Provides group-specific functionality for the Telegram bot:
- Context extraction from group names
- Quote-reply handling
- Group message orchestration
"""

from .group_helper import GroupHelper
from .group_orchestrator import GroupOrchestrator

__all__ = ["GroupHelper", "GroupOrchestrator"]

