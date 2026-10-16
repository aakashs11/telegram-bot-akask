"""Handler-level fail-open coverage for interaction logging."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from telegram_bot import handlers
from telegram_bot.domain.interactions import InteractionEvent
from telegram_bot.runtime import (
    ChatMessage,
    ChatResponse,
    ChatType,
    Platform,
)


class FakeRuntime:
    async def handle(self, message: ChatMessage) -> ChatResponse:
        return ChatResponse(
            text="The response reached the student.",
            metadata={"intent": "explanation"},
        )


class FakeAdapter:
    def __init__(self, message: ChatMessage) -> None:
        self.message = message
        self.sent_responses: list[ChatResponse] = []

    def to_chat_message(self, update, context) -> ChatMessage:
        return self.message

    async def send_response(self, update, context, response: ChatResponse) -> None:
        self.sent_responses.append(response)


class FailingLoggingService:
    def __init__(self) -> None:
        self.events: list[InteractionEvent] = []

    async def log(self, event: InteractionEvent) -> None:
        self.events.append(event)
        raise RuntimeError("logging failed after response delivery")


@pytest.mark.asyncio
async def test_response_succeeds_when_interaction_logging_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_message = ChatMessage(
        platform=Platform.TELEGRAM,
        platform_user_id="123",
        platform_chat_id="123",
        chat_type=ChatType.PRIVATE,
        text="Explain iteration",
    )
    adapter = FakeAdapter(chat_message)
    logging_service = FailingLoggingService()
    fallback_sender = AsyncMock()
    monkeypatch.setattr(handlers, "send_plain", fallback_sender)

    update = SimpleNamespace(
        update_id=987,
        message=SimpleNamespace(
            text=chat_message.text,
            date=datetime(2026, 9, 22, tzinfo=timezone.utc),
        ),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "chat_runtime": FakeRuntime(),
                "telegram_adapter": adapter,
                "interaction_logging_service": logging_service,
            }
        )
    )

    await handlers.handle_message(update, context)

    assert [response.text for response in adapter.sent_responses] == [
        "The response reached the student."
    ]
    fallback_sender.assert_not_awaited()
    assert len(logging_service.events) == 1
    assert logging_service.events[0].telegram_update_id == update.update_id
