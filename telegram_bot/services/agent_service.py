"""
Main agent service using OpenAI function calling.
Orchestrates tool execution based on user queries.
"""

import json
import logging
from typing import Dict, List, Optional, Any

from config.model_config import ModelConfig, ContextConfig, get_model_config, DEFAULT_CONTEXT_CONFIG
from utils.openai_client import get_client
from telegram_bot.tools import BaseTool

logger = logging.getLogger(__name__)


class AgentService:
    """
    Main agent that processes user queries using OpenAI function calling.
    
    Follows SOLID principles:
    - Open/Closed: Add tools without modifying agent code
    - Dependency Inversion: Depends on BaseTool abstraction
    """
    
    def __init__(
        self,
        config: Optional[ModelConfig] = None,
        context_config: Optional[ContextConfig] = None
    ):
        """
        Initialize agent with model and context configuration.
        
        Args:
            config: Model configuration (defaults to 'assistant' config)
            context_config: Context configuration for history limits per chat type
        """
        self.config = config or get_model_config("assistant")
        self.context_config = context_config or DEFAULT_CONTEXT_CONFIG
        self.client = get_client()
        self.tools: Dict[str, BaseTool] = {}
        self.conversation_history: Dict[int, List[Dict]] = {}  # user_id -> messages
        
        logger.info(f"AgentService initialized with model: {self.config.name}")
    
    def register_tool(self, tool: BaseTool):
        """
        Register a new tool for the agent to use.
        
        Args:
            tool: Tool instance implementing BaseTool
        """
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def _build_system_prompt(self, user_profile: Optional[Dict] = None) -> str:
        """Build system prompt with user context using PromptFactory"""
        from telegram_bot.prompts import PromptFactory
        return PromptFactory.build_system_prompt(user_profile)
    
    async def process(
        self,
        user_message: str,
        user_id: int,
        user_profile: Optional[Dict] = None,
        user_service: Optional[Any] = None,
        chat_type: str = "private"
    ) -> str:
        """
        Process user message using agent with tools.
        
        Args:
            user_message: User's message
            user_id: Telegram user ID
            user_profile: Optional user profile dict
            user_service: Optional UserService instance for tools
            chat_type: Type of chat ('private', 'group', 'supergroup')
            
        Returns:
            Agent's response
        """
        try:
            # Build tool definitions for OpenAI
            tool_definitions = [tool.definition for tool in self.tools.values()]
            
            # Get or create conversation history for this user
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []
            
            history = self.conversation_history[user_id]
            
            # Build messages with history
            system_prompt = self._build_system_prompt(user_profile)
            logger.debug(f"System Prompt: {system_prompt}")
            
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # Get history limit based on chat type (Open/Closed principle - configurable)
            history_limit = (
                self.context_config.group_history_limit
                if chat_type in ['group', 'supergroup']
                else self.context_config.private_history_limit
            )
            
            # Add conversation history (limited by chat type)
            messages.extend(history[-history_limit:])
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            logger.debug(f"Sending messages to OpenAI: {json.dumps(messages, indent=2)}")
            
            # Call OpenAI with function calling
            response = await self._call_openai(messages, tool_definitions)
            logger.debug(f"OpenAI Response: {response}")
            
            # Check if tool calls were made
            if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                # Execute tool calls
                tool_results = []
                
                for tool_call in response.choices[0].message.tool_calls:
                    logger.info(f"Processing tool call: {tool_call.function.name} with args {tool_call.function.arguments}")
                    result = await self._execute_tool(
                        tool_call,
                        user_id=user_id,
                        user_profile=user_profile,
                        user_service=user_service
                    )
                    tool_results.append(result)
                
                
                # Combine all tool results
                if tool_results:
                    # Join all non-empty results with newline
                    combined_results = "\n\n".join([r for r in tool_results if r])
                    final_response = combined_results if combined_results else "I couldn't find what you're looking for."
                else:
                    final_response = "I couldn't find what you're looking for."
            else:
                # No tool calls - return text response
                final_response = response.choices[0].message.content or "How can I help you?"
            
            # Update conversation history
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": final_response})
            
            # Keep only last 20 messages (10 exchanges)
            if len(history) > 20:
                self.conversation_history[user_id] = history[-20:]
            
            return final_response
            
        except Exception as e:
            logger.error(f"Error in agent processing: {e}", exc_info=True)
            return "Sorry, I encountered an error. Please try again."
    
    async def _call_openai(self, messages: List[Dict], tools: List[Dict]) -> Any:
        """Call OpenAI API with retries"""
        import asyncio
        
        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=self.config.name,
            messages=messages,
            tools=tools if tools else None,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            frequency_penalty=self.config.frequency_penalty,
            presence_penalty=self.config.presence_penalty
        )
        
        return response
    
    async def _execute_tool(
        self,
        tool_call: Any,
        user_id: int,
        user_profile: Optional[Dict] = None,
        user_service: Optional[Any] = None
    ) -> str:
        """Execute a single tool call"""
        tool_name = tool_call.function.name
        
        if tool_name not in self.tools:
            logger.error(f"Tool not found: {tool_name}")
            return f"Tool '{tool_name}' is not available."
        
        # Parse arguments
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            logger.error(f"Invalid tool arguments: {tool_call.function.arguments}")
            return "Invalid request format."
        
        # Add context to arguments
        arguments['user_id'] = user_id
        arguments['user_profile'] = user_profile
        if user_service:
            arguments['user_service'] = user_service
        
        # Execute tool
        tool = self.tools[tool_name]
        result = await tool.execute(**arguments)
        
        logger.info(f"Tool executed: {tool_name} for user {user_id}")
        
        return result
