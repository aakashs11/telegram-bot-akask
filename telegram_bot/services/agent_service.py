"""
Main agent service using OpenAI Responses API.
Orchestrates tool execution based on user queries with native web search support.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any

from config.model_config import ModelConfig, ContextConfig, get_model_config, DEFAULT_CONTEXT_CONFIG
from utils.openai_client import get_client
from telegram_bot.tools import BaseTool

logger = logging.getLogger(__name__)


class AgentService:
    """
    Main agent that processes user queries using OpenAI Responses API.
    
    Follows SOLID principles:
    - Single Responsibility: Orchestrates tools and API calls
    - Open/Closed: Add tools without modifying agent code
    - Dependency Inversion: Depends on BaseTool abstraction
    
    Uses OpenAI Responses API for:
    - Native web_search_preview tool for real-time web information
    - Custom function tools for domain-specific operations
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
        
        logger.info(f"AgentService initialized with model: {self.config.name} (Responses API)")
    
    def register_tool(self, tool: BaseTool):
        """
        Register a new tool for the agent to use.
        
        Args:
            tool: Tool instance implementing BaseTool
        """
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def _build_system_prompt(
        self,
        user_profile: Optional[Dict] = None,
        is_admin: bool = False,
    ) -> str:
        """Build system prompt with user context using PromptFactory."""
        from telegram_bot.prompts import PromptFactory
        return PromptFactory.build_system_prompt(user_profile, is_admin=is_admin)
    
    def _build_tool_definitions(self) -> List[Dict]:
        """
        Build tool definitions for the Responses API.
        
        Returns:
            List of tool definitions including web_search_preview and custom function tools.
        """
        tools = []
        
        # Add native web search tool
        tools.append({"type": "web_search_preview"})
        
        # Add custom function tools
        for tool in self.tools.values():
            tools.append({
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters_schema
            })
        
        return tools
    
    async def process(
        self,
        user_message: str,
        user_id: int,
        user_profile: Optional[Dict] = None,
        user_service: Optional[Any] = None,
        chat_type: str = "private",
        is_admin: bool = False
    ) -> str:
        """
        Process user message using agent with tools via Responses API.
        
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
            # Get or create conversation history for this user
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []
            
            history = self.conversation_history[user_id]
            
            # Build instructions (system prompt) with user context
            instructions = self._build_system_prompt(user_profile, is_admin=is_admin)
            logger.debug("Built agent instructions (%s chars)", len(instructions))
            
            # Get history limit based on chat type
            history_limit = (
                self.context_config.group_history_limit
                if chat_type in ['group', 'supergroup']
                else self.context_config.private_history_limit
            )
            
            # Build input messages (conversation history + current message)
            input_messages = history[-history_limit:] + [
                {"role": "user", "content": user_message}
            ]
            
            logger.debug(
                "Prepared %s input messages for chat_type=%s (current message=%s chars)",
                len(input_messages),
                chat_type,
                len(user_message),
            )
            
            # Build tool definitions
            tools = self._build_tool_definitions()
            
            # Call Responses API
            response = await self._call_responses_api(instructions, input_messages, tools)
            logger.debug(
                "Responses API returned %s output item(s)",
                len(getattr(response, "output", []) or []),
            )
            
            # Process the response output
            final_response = await self._process_response(
                response,
                user_id=user_id,
                user_profile=user_profile,
                user_service=user_service,
                chat_type=chat_type,
                is_admin=is_admin
            )
            
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
    
    async def _call_responses_api(
        self,
        instructions: str,
        input_messages: List[Dict],
        tools: List[Dict]
    ) -> Any:
        """
        Call OpenAI Responses API.
        
        Args:
            instructions: System instructions (prompt)
            input_messages: Conversation history and current message
            tools: Tool definitions including web_search_preview and custom functions
            
        Returns:
            Response object from Responses API
        """
        response = await asyncio.to_thread(
            self.client.responses.create,
            model=self.config.name,
            instructions=instructions,
            input=input_messages,
            tools=tools,
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_tokens
        )
        
        return response
    
    async def _process_response(
        self,
        response: Any,
        user_id: int,
        user_profile: Optional[Dict] = None,
        user_service: Optional[Any] = None,
        chat_type: str = "private",
        is_admin: bool = False
    ) -> str:
        """
        Process the Responses API response and extract the final text.
        
        Handles:
        - web_search_call: Native web search (automatic, no custom handling needed)
        - function_call: Custom tool calls that need execution
        - message: Text responses with optional citations
        
        Args:
            response: Response object from Responses API
            user_id: Telegram user ID
            user_profile: Optional user profile dict
            user_service: Optional UserService instance for tools
            
        Returns:
            Final text response
        """
        text_parts = []
        function_results = []
        
        for output_item in response.output:
            if output_item.type == "message":
                # Extract text from message content
                text = self._extract_message_text(output_item)
                if text:
                    text_parts.append(text)
                    
            elif output_item.type == "function_call":
                # Execute custom function tool
                logger.info(f"Processing function call: {output_item.name}")
                result = await self._execute_function_call(
                    output_item,
                    user_id=user_id,
                    user_profile=user_profile,
                    user_service=user_service,
                    chat_type=chat_type,
                    is_admin=is_admin
                )
                if result:
                    function_results.append(result)
                    
            elif output_item.type == "web_search_call":
                # Web search is handled automatically by OpenAI
                # The results are incorporated into the message response
                logger.info(f"Web search executed: status={output_item.status}")
        
        # Combine text parts and function results (both may exist for dual-intent queries)
        all_parts = text_parts + function_results
        if all_parts:
            return "\n\n".join(all_parts)
        else:
            return "How can I help you?"
    
    def _extract_message_text(self, message_item: Any) -> Optional[str]:
        """
        Extract text from a message output item.
        
        OpenAI Responses API already includes inline citations like ([domain](url))
        in the response text, so no additional formatting is needed.
        
        Args:
            message_item: Message output item from Responses API
            
        Returns:
            Text content, or None if no text found
        """
        text_parts = []
        
        for content in message_item.content:
            if content.type == "output_text" and hasattr(content, "text"):
                # OpenAI already includes inline citations like ([domain](url))
                # No need for a separate footer - just use the text as-is
                text_parts.append(content.text)
        
        return "\n".join(text_parts) if text_parts else None
    
    async def _execute_function_call(
        self,
        function_call: Any,
        user_id: int,
        user_profile: Optional[Dict] = None,
        user_service: Optional[Any] = None,
        chat_type: str = "private",
        is_admin: bool = False
    ) -> str:
        """
        Execute a custom function tool call.
        
        Args:
            function_call: Function call output item from Responses API
            user_id: Telegram user ID
            user_profile: Optional user profile dict
            user_service: Optional UserService instance for tools
            
        Returns:
            Result from executing the tool
        """
        tool_name = function_call.name
        
        if tool_name not in self.tools:
            logger.error(f"Tool not found: {tool_name}")
            return f"Tool '{tool_name}' is not available."
        
        # Parse arguments
        try:
            arguments = json.loads(function_call.arguments)
        except json.JSONDecodeError:
            logger.error(f"Invalid tool arguments: {function_call.arguments}")
            return "Invalid request format."
        
        # Add context to arguments
        arguments['user_id'] = user_id
        arguments['user_profile'] = user_profile
        if user_service:
            arguments['user_service'] = user_service
        arguments['chat_type'] = chat_type
        arguments['is_admin'] = is_admin
        
        # Execute tool
        tool = self.tools[tool_name]
        result = await tool.execute(**arguments)
        
        logger.info(f"Tool executed: {tool_name} for user {user_id}")
        
        return result
