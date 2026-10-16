"""Anonymous group-admin posts skip moderation and still need a mention."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from telegram_bot.runtime.chat_runtime import ChatRuntime
from telegram_bot.runtime.contracts import ChatMessage, ChatType, Platform, ReplyMode

ANONYMOUS_ADMIN_ID = "1087968824"
GROUP_ID = "-1001234567890"


def _message(**overrides) -> ChatMessage:
    values = {
        "platform": Platform.TELEGRAM,
        "platform_user_id": ANONYMOUS_ADMIN_ID,
        "platform_chat_id": GROUP_ID,
        "chat_type": ChatType.SUPERGROUP,
        "text": "https://youtu.be/example",
        "is_bot_mentioned": False,
        "metadata": {"skip_moderation": True},
    }
    values.update(overrides)
    return ChatMessage(**values)


@pytest.mark.asyncio
async def test_anonymous_group_admin_post_is_not_moderated() -> None:
    moderator = AsyncMock()
    runtime = ChatRuntime(agent=AsyncMock(), user_service=AsyncMock(), content_moderator=moderator)

    response = await runtime.handle(_message())

    moderator.check.assert_not_awaited()
    assert response.reply_mode == ReplyMode.SILENT


@pytest.mark.asyncio
async def test_same_user_without_the_flag_is_moderated() -> None:
    moderator = AsyncMock()
    moderator.check.return_value = SimpleNamespace(is_flagged=False)
    runtime = ChatRuntime(agent=AsyncMock(), user_service=AsyncMock(), content_moderator=moderator)

    await runtime.handle(_message(metadata={}))

    moderator.check.assert_awaited_once()
