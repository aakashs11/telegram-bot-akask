"""Google Sheets adapter for temporary interaction-log dual writes."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from gspread.exceptions import WorksheetNotFound

from telegram_bot.domain.interactions import InteractionEvent, InteractionRepository


class SheetsInteractionRepository(InteractionRepository):
    """Append interactions to Sheets without blocking the async event loop."""

    WORKSHEET_NAME = "Logs"
    HEADERS = [
        "Timestamp",
        "User ID",
        "User Message",
        "Bot Response",
        "Screener",
        "Intent",
        "Entities",
        "Event ID",
    ]

    def __init__(self, sheet_provider: Callable[[], Any]) -> None:
        self._sheet_provider = sheet_provider
        self._write_lock = asyncio.Lock()
        self._header_initialized = False

    async def add(self, event: InteractionEvent) -> bool:
        # gspread is synchronous. Serialize access to its client and move the
        # complete operation, including lazy authentication, to a worker thread.
        async with self._write_lock:
            await asyncio.to_thread(self._append, event)
        return True

    def _append(self, event: InteractionEvent) -> None:
        sheet = self._sheet_provider()
        if sheet is None:
            raise RuntimeError("Google Sheet is unavailable")

        try:
            worksheet = sheet.worksheet(self.WORKSHEET_NAME)
        except WorksheetNotFound:
            worksheet = sheet.add_worksheet(
                title=self.WORKSHEET_NAME,
                rows=1000,
                cols=len(self.HEADERS),
            )
            worksheet.append_row(self.HEADERS)
            self._header_initialized = True

        if not self._header_initialized:
            headers = worksheet.row_values(1)
            event_id_header = headers[7].strip() if len(headers) >= 8 else ""
            if event_id_header and event_id_header != self.HEADERS[7]:
                raise RuntimeError("Logs column H is already used by another field")
            if not event_id_header:
                worksheet.update_cell(1, 8, self.HEADERS[7])
            self._header_initialized = True

        worksheet.append_row(
            [
                event.occurred_at.isoformat(),
                event.telegram_user_id,
                event.user_message,
                event.bot_response,
                event.screener_output,
                event.intent_output,
                event.entities_output,
                str(event.event_id),
            ]
        )
