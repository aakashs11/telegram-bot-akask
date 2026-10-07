"""Regression tests for moderation of messages sent on behalf of a chat."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")

from telegram_bot.services.group.group_orchestrator import GroupOrchestrator
from telegram_bot.services.moderation.content_moderator import ModerationResult


GROUP_ID = -1001234567890
ANONYMOUS_ADMIN_ID = 1087968824


class AnonymousAdminModerationTests(unittest.IsolatedAsyncioTestCase):
    async def _handle(self, user_id, sender_chat=None):
        moderator = SimpleNamespace(check=AsyncMock(return_value=ModerationResult(False)))
        warnings = SimpleNamespace(add_warning=AsyncMock())
        orchestrator = GroupOrchestrator(
            content_moderator=moderator,
            warning_service=warnings,
        )
        message = SimpleNamespace(sender_chat=sender_chat, delete=AsyncMock())
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=GROUP_ID, title="Study group", type="supergroup"),
            effective_user=SimpleNamespace(username="GroupAnonymousBot"),
            message=message,
        )
        await orchestrator.handle_message(
            update=update,
            context=SimpleNamespace(),
            user_message="https://youtu.be/example",
            user_id=user_id,
            bot_username="akask_ai_bot",
        )
        return moderator, warnings, message

    async def test_anonymous_group_admin_post_is_not_moderated(self):
        moderator, warnings, message = await self._handle(
            ANONYMOUS_ADMIN_ID,
            sender_chat=SimpleNamespace(id=GROUP_ID, type="supergroup"),
        )

        moderator.check.assert_not_awaited()
        warnings.add_warning.assert_not_awaited()
        message.delete.assert_not_awaited()

    async def test_other_chat_sender_is_still_moderated(self):
        moderator, _, _ = await self._handle(
            ANONYMOUS_ADMIN_ID,
            sender_chat=SimpleNamespace(id=-1009999999999, type="channel"),
        )

        moderator.check.assert_awaited_once_with("https://youtu.be/example")

    async def test_fake_admin_id_without_group_sender_is_still_moderated(self):
        moderator, _, _ = await self._handle(ANONYMOUS_ADMIN_ID)

        moderator.check.assert_awaited_once_with("https://youtu.be/example")


if __name__ == "__main__":
    unittest.main()
