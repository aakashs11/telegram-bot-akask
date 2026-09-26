"""Unit coverage for feature-flagged interaction logging."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from telegram_bot.domain.interactions import InteractionEvent
from telegram_bot.services.interaction_logging_service import (
    InteractionLogMode,
    InteractionLoggingService,
)


@dataclass
class FakeRepository:
    inserted: bool = True
    error: Exception | None = None
    events: list[InteractionEvent] = field(default_factory=list)

    async def add(self, event: InteractionEvent) -> bool:
        self.events.append(event)
        if self.error is not None:
            raise self.error
        return self.inserted


def event() -> InteractionEvent:
    return InteractionEvent(
        telegram_user_id=123,
        telegram_update_id=456,
        user_message="How does a loop work?",
        bot_response="A loop repeats a block of instructions.",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected_sheet_writes", "expected_postgres_writes"),
    [
        (InteractionLogMode.SHEET, 1, 0),
        (InteractionLogMode.DUAL, 1, 1),
        (InteractionLogMode.POSTGRES, 0, 1),
        (InteractionLogMode.OFF, 0, 0),
    ],
)
async def test_mode_selects_only_configured_sinks(
    mode: InteractionLogMode,
    expected_sheet_writes: int,
    expected_postgres_writes: int,
) -> None:
    sheet = FakeRepository()
    postgres = FakeRepository()
    service = InteractionLoggingService(
        mode=mode,
        sheet_repository=sheet,
        postgres_repository=postgres,
    )

    report = await service.log(event())

    assert report.mode is mode
    assert report.success is True
    assert len(sheet.events) == expected_sheet_writes
    assert len(postgres.events) == expected_postgres_writes


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_sink", ["sheet", "postgres"])
async def test_dual_mode_isolates_one_sink_failure(failed_sink: str) -> None:
    sheet = FakeRepository(
        error=RuntimeError("sheet unavailable") if failed_sink == "sheet" else None
    )
    postgres = FakeRepository(
        error=RuntimeError("database unavailable")
        if failed_sink == "postgres"
        else None
    )
    service = InteractionLoggingService(
        mode="dual",
        sheet_repository=sheet,
        postgres_repository=postgres,
    )

    report = await service.log(event())

    assert len(sheet.events) == 1
    assert len(postgres.events) == 1
    assert report.success is False
    results = {result.sink: result for result in report.sink_results}
    assert results[failed_sink].success is False
    assert results[failed_sink].error_type == "RuntimeError"
    other_sink = "postgres" if failed_sink == "sheet" else "sheet"
    assert results[other_sink].success is True


@pytest.mark.asyncio
async def test_dual_mode_passes_same_event_and_event_id_to_both_sinks() -> None:
    sheet = FakeRepository()
    postgres = FakeRepository()
    service = InteractionLoggingService(
        mode="dual",
        sheet_repository=sheet,
        postgres_repository=postgres,
    )
    interaction = event()

    report = await service.log(interaction)

    assert sheet.events == [interaction]
    assert postgres.events == [interaction]
    assert sheet.events[0] is postgres.events[0]
    assert report.event_id == str(interaction.event_id)


@pytest.mark.asyncio
async def test_missing_repository_is_reported_without_raising() -> None:
    service = InteractionLoggingService(mode="postgres")

    report = await service.log(event())

    assert report.success is False
    assert report.sink_results[0].sink == "postgres"
    assert report.sink_results[0].error_type == "RuntimeError"
