"""Shared, side-effect-free helpers for interaction-log migration scripts."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telegram_bot.domain.interactions import InteractionEvent

PAYLOAD_HEADERS = (
    "Timestamp",
    "User ID",
    "User Message",
    "Bot Response",
    "Screener",
    "Intent",
    "Entities",
)
EVENT_ID_HEADER = "Event ID"
BACKFILL_EVENT_NAMESPACE = UUID("8b63542f-49a8-5a18-b454-e86fdcd4a47f")


@dataclass(frozen=True, slots=True)
class SourceRow:
    """One physical source row, retaining its location and exact cells."""

    row_number: int
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ValidatedRow:
    """A validated source row and its normalized database representation."""

    source: SourceRow
    event: InteractionEvent
    payload: tuple[str, ...]
    event_id_from_sheet: UUID | None


@dataclass(frozen=True, slots=True)
class RejectedRow:
    """A malformed source row that must be explicitly accounted for."""

    row_number: int
    reason: str
    values: tuple[str, ...]


def validate_headers(headers: Sequence[str]) -> bool:
    """Validate the seven legacy headers and optional dual-write event ID."""
    normalized = tuple(value.strip().lstrip("\ufeff") for value in headers)
    if normalized[:7] != PAYLOAD_HEADERS:
        raise ValueError(
            "source headers must begin with exactly: " + ", ".join(PAYLOAD_HEADERS)
        )
    if len(normalized) not in {7, 8}:
        raise ValueError("source must contain seven columns, plus optional Event ID")
    if len(normalized) == 8 and normalized[7] != EVENT_ID_HEADER:
        raise ValueError(f"eighth column must be {EVENT_ID_HEADER!r}")
    return len(normalized) == 8


def iter_csv_rows(path: Path) -> tuple[bool, Iterator[SourceRow]]:
    """Open a CSV export and stream physical rows without loading it in memory."""
    handle = path.open("r", encoding="utf-8-sig", newline="")
    reader = csv.reader(handle)
    try:
        headers = next(reader)
        has_event_id = validate_headers(headers)
    except Exception:
        handle.close()
        raise

    def rows() -> Iterator[SourceRow]:
        try:
            for row_number, row in enumerate(reader, start=2):
                yield SourceRow(row_number, tuple(row))
        finally:
            handle.close()

    return has_event_id, rows()


def rows_from_sheet_values(values: Sequence[Sequence[object]]) -> tuple[bool, Iterator[SourceRow]]:
    """Validate and stream values returned by gspread's read-only get_all_values."""
    if not values:
        raise ValueError("source worksheet is empty")
    headers = tuple(str(value) for value in values[0])
    has_event_id = validate_headers(headers)

    def rows() -> Iterator[SourceRow]:
        for index, row in enumerate(values[1:], start=2):
            cells = tuple(str(value) for value in row)
            # The Sheets API may omit trailing empty cells. They are present
            # logically because the validated header fixes the row width.
            if len(cells) < len(headers):
                cells += ("",) * (len(headers) - len(cells))
            yield SourceRow(index, cells)

    return has_event_id, rows()


def load_sheet_rows(
    *,
    sheet_id: str,
    worksheet_name: str,
    credentials_file: Path | None,
) -> tuple[bool, Iterator[SourceRow]]:
    """Read a worksheet without changing it, using explicit or ADC credentials."""
    import google.auth
    import gspread

    if credentials_file:
        client = gspread.service_account(filename=str(credentials_file))
    else:
        credentials, _ = google.auth.default()
        client = gspread.authorize(credentials)
    worksheet = client.open_by_key(sheet_id).worksheet(worksheet_name)
    return rows_from_sheet_values(worksheet.get_all_values())


def timezone_from_name(name: str) -> ZoneInfo:
    """Resolve an explicit IANA timezone with an actionable error."""
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown IANA timezone: {name}") from exc


def parse_source_timestamp(raw: str, source_timezone: ZoneInfo) -> datetime:
    """Parse legacy timestamps, applying source timezone only when no offset exists."""
    value = raw.strip()
    if not value:
        raise ValueError("Timestamp is empty")

    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        for date_format in ("%m/%d/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
            try:
                parsed = datetime.strptime(value, date_format)
                break
            except ValueError:
                continue
    if parsed is None:
        raise ValueError("Timestamp is not a supported ISO or legacy datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=source_timezone)
    return parsed.astimezone(timezone.utc)


def deterministic_source_ref(source_id: str, row_number: int) -> str:
    """Build the stable idempotency key used by every rerun."""
    normalized = source_id.strip()
    if not normalized or ":" in normalized:
        raise ValueError("source ID must be non-empty and contain no colon")
    if row_number < 2:
        raise ValueError("source row number must include the header offset")
    return f"sheet:{normalized}:row:{row_number}"


def validate_row(
    source: SourceRow,
    *,
    source_id: str,
    source_timezone: ZoneInfo,
    has_event_id: bool,
) -> ValidatedRow:
    """Validate all seven payload cells and construct a deterministic event."""
    expected_columns = 8 if has_event_id else 7
    if len(source.values) != expected_columns:
        raise ValueError(
            f"expected {expected_columns} columns, found {len(source.values)}"
        )

    timestamp_raw, user_id_raw, *text_fields = source.values[:7]
    occurred_at = parse_source_timestamp(timestamp_raw, source_timezone)
    try:
        telegram_user_id = int(user_id_raw.strip())
    except ValueError as exc:
        raise ValueError("User ID must be an integer") from exc
    if not user_id_raw.strip():
        raise ValueError("User ID is empty")

    source_ref = deterministic_source_ref(source_id, source.row_number)
    sheet_event_id: UUID | None = None
    if has_event_id and source.values[7].strip():
        try:
            sheet_event_id = UUID(source.values[7].strip())
        except ValueError as exc:
            raise ValueError("Event ID is not a UUID") from exc

    payload = (
        timestamp_raw,
        str(telegram_user_id),
        *tuple(text_fields),
    )
    event = InteractionEvent(
        event_id=sheet_event_id or uuid5(BACKFILL_EVENT_NAMESPACE, source_ref),
        telegram_user_id=telegram_user_id,
        occurred_at=occurred_at,
        user_message=text_fields[0],
        bot_response=text_fields[1],
        screener_output=text_fields[2],
        intent_output=text_fields[3],
        entities_output=text_fields[4],
        source_ref=source_ref,
        source_timestamp_raw=timestamp_raw,
    )
    return ValidatedRow(source, event, payload, sheet_event_id)


def canonical_payload(
    payload: Sequence[str],
    *,
    source_timezone: ZoneInfo,
) -> tuple[str, ...]:
    """Canonicalize typed fields while retaining exact text-field bytes."""
    if len(payload) != 7:
        raise ValueError("payload must contain exactly seven fields")
    occurred_at = parse_source_timestamp(payload[0], source_timezone)
    timestamp = occurred_at.isoformat(timespec="microseconds")
    user_id = str(int(payload[1].strip()))
    return (timestamp, user_id, *tuple(payload[2:]))


def field_hashes(
    payload: Sequence[str],
    *,
    source_timezone: ZoneInfo,
) -> tuple[str, ...]:
    """Hash each canonical field so reconciliation never emits personal data."""
    return tuple(
        hashlib.sha256(value.encode("utf-8")).hexdigest()
        for value in canonical_payload(payload, source_timezone=source_timezone)
    )


def payload_hash(
    payload: Sequence[str],
    *,
    source_timezone: ZoneInfo,
) -> str:
    """Hash a length-prefixed canonical payload without delimiter ambiguity."""
    digest = hashlib.sha256()
    for value in canonical_payload(payload, source_timezone=source_timezone):
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def batched(rows: Iterable[ValidatedRow], size: int) -> Iterator[list[ValidatedRow]]:
    """Yield bounded lists from a streaming row source."""
    if size < 1:
        raise ValueError("batch size must be at least 1")
    batch: list[ValidatedRow] = []
    for row in rows:
        batch.append(row)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def write_rejected_rows(path: Path, rejected: Iterable[RejectedRow]) -> None:
    """Write a deterministic review report without exposing rows to logs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("row_number", "reason", "raw_values_json"))
        for row in rejected:
            writer.writerow(
                (
                    row.row_number,
                    row.reason,
                    json.dumps(row.values, ensure_ascii=False),
                )
            )
