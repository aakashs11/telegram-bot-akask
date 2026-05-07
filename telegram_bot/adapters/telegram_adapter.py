import logging
from typing import List, Optional

from telegram import Message, Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from config.settings import ADMIN_USER_IDS
from telegram_bot.runtime import (
    ChatMessage,
    ChatResponse,
    ChatType,
    Platform,
    ReplyMode,
    ResponseVisibility,
)
from telegram_bot.services.message_service import send_response as send_telegram_response
from telegram_bot.services.message_service import send_to_user
from utils.common import schedule_message_deletion

logger = logging.getLogger(__name__)


class TelegramAdapter:
    """Translate between python-telegram-bot objects and runtime contracts."""

    AUTO_DELETE_DELAY = 30

    def to_chat_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> Optional[ChatMessage]:
        if not update.message or not update.message.text:
            return None

        user = update.effective_user
        chat = update.effective_chat
        text = update.message.text
        bot_username = context.bot.username or ""
        chat_type = (
            ChatType(chat.type)
            if chat.type in ChatType._value2member_map_
            else ChatType.PRIVATE
        )

        return ChatMessage(
            platform=Platform.TELEGRAM,
            platform_user_id=str(user.id),
            platform_chat_id=str(chat.id),
            chat_type=chat_type,
            text=text,
            username=user.username or "",
            message_id=str(update.message.message_id),
            reply_to_text=self._extract_reply_text(update.message),
            is_bot_mentioned=bool(bot_username and f"@{bot_username}" in text),
            bot_username=bot_username,
            group_title=chat.title or "",
            is_admin=user.id in ADMIN_USER_IDS,
            metadata={
                "telegram_user_id": user.id,
                "telegram_chat_id": chat.id,
                "first_name": user.first_name,
            },
        )

    async def send_response(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        response: ChatResponse,
    ) -> List[Message]:
        if response.reply_mode == ReplyMode.SILENT or not response.text:
            return []

        parse_mode = response.metadata.get("parse_mode", "Markdown")

        if response.reply_mode == ReplyMode.DM:
            user_id = update.effective_user.id
            msg = await send_to_user(context, user_id, response.text, parse_mode=parse_mode)
            return [msg] if msg else []

        if response.visibility == ResponseVisibility.EPHEMERAL:
            try:
                sent = await update.message.reply_text(response.text, parse_mode=parse_mode)
            except TelegramError as exc:
                logger.warning("Markdown send failed, retrying plain text: %s", exc)
                sent = await update.message.reply_text(response.text)

            schedule_message_deletion(
                bot=context.bot,
                chat_id=sent.chat_id,
                message_id=sent.message_id,
                delay=self.AUTO_DELETE_DELAY,
            )
            return [sent]

        return await send_telegram_response(
            update,
            response.text,
            parse_mode=parse_mode,
            disable_preview=response.metadata.get("disable_preview", True),
        )

    def _extract_reply_text(self, message: Message) -> Optional[str]:
        if message.reply_to_message and message.reply_to_message.text:
            return message.reply_to_message.text
        return None
