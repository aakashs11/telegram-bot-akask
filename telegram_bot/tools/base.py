"""
Base interface for agent tools following SOLID principles.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseTool(ABC):
    """
    Abstract base class for all agent tools.
    
    Follows SOLID principles:
    - Single Responsibility: Each tool does one thing
    - Open/Closed: Easy to add new tools without modifying existing code
    - Liskov Substitution: All tools are interchangeable
    - Interface Segregation: Minimal interface
    - Dependency Inversion: Agent depends on abstractions
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for OpenAI function calling"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the tool does"""
        pass
    
    @property
    @abstractmethod
    def parameters_schema(self) -> Dict[str, Any]:
        """
        JSON schema for tool parameters.
        
        Returns:
            Dict with OpenAI function calling parameter schema
        """
        pass
    
    @property
    def definition(self) -> Dict[str, Any]:
        """
        Complete OpenAI function definition.
        Combines name, description, and parameters.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema
            }
        }
    
    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """
        Execute the tool with given parameters.
        
        Args:
            **kwargs: Tool-specific parameters
            
        Returns:
            String response to send to user
        """
        pass
