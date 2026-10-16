"""Feature-flagged, fail-open interaction logging orchestration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from time import perf_counter
from typing import Optional

from telegram_bot.domain.interactions import InteractionEvent, InteractionRepository

logger = logging.getLogger(__name__)


class InteractionLogMode(str, Enum):
    SHEET = "sheet"
    DUAL = "dual"
    POSTGRES = "postgres"
    OFF = "off"


@dataclass(frozen=True, slots=True)
class SinkWriteResult:
    sink: str
    success: bool
    inserted: Optional[bool]
    latency_ms: float
    error_type: Optional[str] = None


@dataclass(frozen=True, slots=True)
class InteractionWriteReport:
    event_id: str
    mode: InteractionLogMode
    sink_results: tuple[SinkWriteResult, ...]

    @property
    def success(self) -> bool:
        return all(result.success for result in self.sink_results)


class InteractionLoggingService:
    """Write to configured sinks independently and never raise sink failures."""

    def __init__(
        self,
        *,
        mode: str | InteractionLogMode,
        sheet_repository: Optional[InteractionRepository] = None,
        postgres_repository: Optional[InteractionRepository] = None,
        write_timeout_seconds: float = 5.0,
    ) -> None:
        self.mode = InteractionLogMode(mode)
        self._sheet_repository = sheet_repository
        self._postgres_repository = postgres_repository
        self._write_timeout_seconds = write_timeout_seconds

    async def log(self, event: InteractionEvent) -> InteractionWriteReport:
        repositories = self._selected_repositories()
        results = tuple(
            await asyncio.gather(
                *(
                    self._write_sink(sink, repository, event)
                    for sink, repository in repositories
                )
            )
        )
        report = InteractionWriteReport(
            event_id=str(event.event_id),
            mode=self.mode,
            sink_results=results,
        )

        if self.mode == InteractionLogMode.DUAL:
            log_method = logger.info if report.success else logger.warning
            log_method(
                (
                    "interaction_dual_write_complete "
                    if report.success
                    else "interaction_dual_write_incomplete "
                )
                + "event_id=%s successful_sinks=%s/%s",
                report.event_id,
                sum(result.success for result in results),
                len(results),
                extra={
                    "event_id": report.event_id,
                    "mode": self.mode.value,
                    "sink_count": len(results),
                    "successful_sink_count": sum(
                        result.success for result in results
                    ),
                },
            )
        return report

    def _selected_repositories(
        self,
    ) -> tuple[tuple[str, Optional[InteractionRepository]], ...]:
        if self.mode == InteractionLogMode.OFF:
            return ()
        if self.mode == InteractionLogMode.SHEET:
            return (("sheet", self._sheet_repository),)
        if self.mode == InteractionLogMode.POSTGRES:
            return (("postgres", self._postgres_repository),)
        return (
            ("sheet", self._sheet_repository),
            ("postgres", self._postgres_repository),
        )

    async def _write_sink(
        self,
        sink: str,
        repository: Optional[InteractionRepository],
        event: InteractionEvent,
    ) -> SinkWriteResult:
        started_at = perf_counter()
        inserted: Optional[bool] = None
        error_type: Optional[str] = None

        try:
            if repository is None:
                raise RuntimeError("sink_not_configured")
            inserted = await asyncio.wait_for(
                repository.add(event),
                timeout=self._write_timeout_seconds,
            )
            success = True
        except asyncio.TimeoutError:
            success = False
            error_type = "timeout"
        except Exception as exc:
            success = False
            error_type = type(exc).__name__

        latency_ms = round((perf_counter() - started_at) * 1000, 2)
        result = SinkWriteResult(
            sink=sink,
            success=success,
            inserted=inserted,
            latency_ms=latency_ms,
            error_type=error_type,
        )
        (logger.info if success else logger.warning)(
            (
                "interaction_sink_write event_id=%s sink=%s success=%s inserted=%s "
                "latency_ms=%s error_type=%s"
            ),
            event.event_id,
            sink,
            success,
            inserted,
            latency_ms,
            error_type,
            extra={
                "event_id": str(event.event_id),
                "sink": sink,
                "success": success,
                "inserted": inserted,
                "latency_ms": latency_ms,
                "error_type": error_type,
            },
        )
        return result
