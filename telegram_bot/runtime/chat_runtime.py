import logging
from typing import Any, Dict, Optional

from telegram_bot.runtime.contracts import (
    ChatMessage,
    ChatResponse,
    ChatType,
    ReplyMode,
    ResponseVisibility,
)
from telegram_bot.services.group.group_helper import GroupHelper

logger = logging.getLogger(__name__)


class ChatRuntime:
    """
    Platform-neutral message runtime.

    Telegram-specific parsing and delivery stay in the adapter. This service owns
    the shared decision path that future platform adapters can reuse.
    """

    def __init__(
        self,
        agent: Any,
        user_service: Any,
        content_moderator: Optional[Any] = None,
        group_helper: Optional[GroupHelper] = None,
    ):
        self.agent = agent
        self.user_service = user_service
        self.content_moderator = content_moderator
        self.group_helper = group_helper or GroupHelper()

    async def handle(self, message: ChatMessage) -> ChatResponse:
        if not message.text.strip():
            return ChatResponse(reply_mode=ReplyMode.SILENT, metadata={"route": "empty"})

        if message.chat_type in (ChatType.GROUP, ChatType.SUPERGROUP):
            return await self._handle_group_message(message)

        return await self._handle_private_message(message)

    async def _handle_private_message(self, message: ChatMessage) -> ChatResponse:
        user_id = self._numeric_user_id(message)

        mod_result = await self._moderate(message.text)
        if mod_result and mod_result.is_flagged:
            return ChatResponse(
                text="⚠️ Your message was flagged. Please use appropriate language.",
                reply_mode=ReplyMode.REPLY,
                metadata={
                    "route": "moderation_flagged",
                    "category": mod_result.category,
                    "raw_response": mod_result.raw_response,
                },
            )

        user_profile = await self._get_user_profile(user_id, message.username)
        response = await self.agent.process(
            user_message=message.text,
            user_id=user_id,
            user_profile=user_profile,
            user_service=self.user_service,
            chat_type="private",
            is_admin=message.is_admin,
        )

        return ChatResponse(
            text=response,
            reply_mode=ReplyMode.REPLY,
            metadata={
                "route": "private_agent",
                "intent": "agent",
                "user_id": user_id,
            },
        )

    async def _handle_group_message(self, message: ChatMessage) -> ChatResponse:
        user_id = self._numeric_user_id(message)
        is_admin = message.is_admin

        moderation_text = self._strip_bot_mention(message.text, message.bot_username)
        if not is_admin:
            mod_result = await self._moderate(moderation_text)
            if mod_result and mod_result.is_flagged:
                return ChatResponse(
                    reply_mode=ReplyMode.SILENT,
                    metadata={
                        "route": "moderation_flagged",
                        "category": mod_result.category,
                        "raw_response": mod_result.raw_response,
                        "action": "group_violation",
                    },
                )

        if not message.is_bot_mentioned:
            return ChatResponse(
                reply_mode=ReplyMode.SILENT,
                metadata={"route": "group_not_mentioned"},
            )

        clean_text = self._strip_bot_mention(message.text, message.bot_username)
        if not clean_text and not message.reply_to_text:
            return ChatResponse(
                text="Hi! How can I help you? 💬",
                reply_mode=ReplyMode.REPLY,
                visibility=ResponseVisibility.EPHEMERAL,
                metadata={"route": "group_empty_mention"},
            )

        group_context = self.group_helper.extract_from_group_name(message.group_title)
        enriched_message = self.group_helper.build_context_message(
            user_message=clean_text,
            replied_text=message.reply_to_text,
            group_context=group_context,
        )

        user_profile = await self._get_user_profile(user_id, message.username)
        has_context = is_admin or self.group_helper.has_sufficient_context(
            user_message=clean_text,
            group_context=group_context,
            user_profile=user_profile,
        )

        if not has_context:
            return ChatResponse(
                text=(
                    "💬 *Need more details!*\n\n"
                    "Please DM me with your class and subject, "
                    "or ask in full like: \"Class 12 AI sample papers\""
                ),
                reply_mode=ReplyMode.REPLY,
                visibility=ResponseVisibility.EPHEMERAL,
                metadata={"route": "group_insufficient_context"},
            )

        response = await self.agent.process(
            user_message=enriched_message,
            user_id=user_id,
            user_profile=user_profile,
            user_service=self.user_service,
            chat_type="group",
            is_admin=is_admin,
        )

        return ChatResponse(
            text=response,
            reply_mode=ReplyMode.REPLY,
            metadata={
                "route": "group_agent",
                "intent": "agent",
                "user_id": user_id,
                "group_context": group_context,
            },
        )

    async def _moderate(self, text: str) -> Optional[Any]:
        if not self.content_moderator:
            return None
        return await self.content_moderator.check(text)

    async def _get_user_profile(self, user_id: int, username: str) -> Dict[str, Any]:
        if not self.user_service:
            return {}
        return await self.user_service.get_user_profile(user_id=user_id, username=username)

    def _numeric_user_id(self, message: ChatMessage) -> int:
        if message.metadata.get("internal_user_id") is not None:
            return int(message.metadata["internal_user_id"])
        return int(message.platform_user_id)

    def _strip_bot_mention(self, text: str, bot_username: str) -> str:
        if not bot_username:
            return text.strip()
        return text.replace(f"@{bot_username}", "").strip()
