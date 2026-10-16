#!/usr/bin/env python3
"""Copy the Warnings sheet into the warnings table.

Dry-run is the default. --apply upserts on telegram_user_id and telegram_chat_id.
The sheet is not modified.

last_warning on the sheet is a naive timestamp. Pass the timezone of the
machine that wrote it. UTC is the right guess for Cloud Run. The flag does
not change a timestamp that already has an offset.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from scripts.interaction_log_migration import (
    RejectedRow,
    SourceRow,
    parse_source_timestamp,
    timezone_from_name,
    write_rejected_rows,
)
from telegram_bot.infrastructure.database import async_database_url
from telegram_bot.infrastructure.postgres_warnings import warnings

WARNING_HEADERS = (
    "user_id",
    "chat_id",
    "username",
    "warning_count",
    "last_reason",
    "last_warning",
    "banned",
)


@dataclass(frozen=True, slots=True)
class WarningRow:
    """One validated Warnings-sheet row."""

    row_number: int
    telegram_user_id: int
    telegram_chat_id: int
    username: str
    warning_count: int
    last_reason: str
    last_warning: datetime
    banned: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the Warnings sheet and optionally upsert it. "
            "Dry-run is the default; only --apply writes PostgreSQL."
        )
    )
    parser.add_argument("--csv", type=Path, help="Warnings CSV export")
    parser.add_argument("--sheet-id", help="Google Sheet ID. Defaults to SHEET_ID")
    parser.add_argument("--worksheet", default="Warnings")
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--source-timezone", required=True)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--rejects-file",
        type=Path,
        default=Path("artifacts/warnings-rejected.csv"),
    )
    parser.add_argument("--database-url")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def validate_warning_headers(headers: tuple[str, ...]) -> None:
    """Require the seven Warnings columns, in order."""
    normalized = tuple(value.strip().lstrip("\ufeff") for value in headers)
    if normalized[:7] != WARNING_HEADERS:
        raise ValueError(
            "source headers must begin with exactly: " + ", ".join(WARNING_HEADERS)
        )


def _sheet_client(credentials_file: Path | None):
    import gspread

    path = credentials_file or Path("service_account.json")
    if path.is_file():
        return gspread.service_account(filename=str(path))
    import google.auth

    try:
        credentials, _ = google.auth.default()
    except Exception as exc:
        raise ValueError(
            "No service_account.json in this directory, and Google "
            "Application Default Credentials are not set. Pass --credentials-file."
        ) from exc
    return gspread.authorize(credentials)


def iter_warning_rows(args: argparse.Namespace) -> Iterator[SourceRow]:
    """Stream Warnings rows from a CSV or from the live worksheet."""
    if args.csv and args.sheet_id:
        raise ValueError("pass either --csv or --sheet-id, not both")
    if args.csv:
        handle = args.csv.open("r", encoding="utf-8-sig", newline="")
        reader = csv.reader(handle)
        try:
            headers = tuple(next(reader))
            validate_warning_headers(headers)
        except Exception:
            handle.close()
            raise

        def csv_rows() -> Iterator[SourceRow]:
            try:
                width = max(len(headers), 7)
                for row_number, row in enumerate(reader, start=2):
                    cells = tuple(row)
                    if len(cells) < width:
                        cells += ("",) * (width - len(cells))
                    yield SourceRow(row_number, cells[:width])
            finally:
                handle.close()

        return csv_rows()

    sheet_id = args.sheet_id or os.getenv("SHEET_ID")
    if not sheet_id:
        raise ValueError("pass --csv or --sheet-id, or set SHEET_ID")
    import gspread

    try:
        values = (
            _sheet_client(args.credentials_file)
            .open_by_key(sheet_id)
            .worksheet(args.worksheet)
            .get_all_values()
        )
    except gspread.WorksheetNotFound as exc:
        raise ValueError(f"{args.worksheet} worksheet was not found") from exc
    if not values:
        raise ValueError("source worksheet is empty")
    headers = tuple(str(value) for value in values[0])
    validate_warning_headers(headers)
    width = max(len(headers), 7)

    def sheet_rows() -> Iterator[SourceRow]:
        for row_number, row in enumerate(values[1:], start=2):
            cells = tuple(str(value) for value in row)
            if len(cells) < width:
                cells += ("",) * (width - len(cells))
            yield SourceRow(row_number, cells[:width])

    return sheet_rows()


def _integer_id(value: str, label: str) -> int:
    text = value.strip()
    if not text or not text.lstrip("-").isdigit():
        raise ValueError(f"{label} is not an integer")
    return int(text)


def prefer_warning(current: WarningRow, candidate: WarningRow) -> WarningRow:
    """Keep the higher count. The sheet appended a new row on later warnings."""
    if candidate.warning_count > current.warning_count:
        return candidate
    if (
        candidate.warning_count == current.warning_count
        and candidate.last_warning >= current.last_warning
    ):
        return candidate
    return current


def validate_warning_row(source: SourceRow, source_timezone) -> WarningRow:
    """Turn one Warnings row into a record, or raise ValueError."""
    if len(source.values) < 7:
        raise ValueError(f"expected at least 7 columns, found {len(source.values)}")
    user_id, chat_id, username, count, reason, warned_at, banned = (
        cell.strip() for cell in source.values[:7]
    )
    if not any((user_id, chat_id, username, count, reason, warned_at, banned)):
        raise ValueError("empty row")
    telegram_user_id = _integer_id(user_id, "user_id")
    telegram_chat_id = _integer_id(chat_id, "chat_id")
    if not count.isdigit():
        raise ValueError("warning_count is not a non-negative integer")
    banned_text = banned.upper()
    if banned_text not in {"TRUE", "FALSE"}:
        raise ValueError("banned must be TRUE or FALSE")
    return WarningRow(
        row_number=source.row_number,
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        username=username,
        warning_count=int(count),
        last_reason=reason,
        last_warning=parse_source_timestamp(warned_at, source_timezone),
        banned=banned_text == "TRUE",
    )


async def upsert_batch(engine: AsyncEngine, batch: list[WarningRow]) -> tuple[int, int]:
    keys = [(row.telegram_user_id, row.telegram_chat_id) for row in batch]
    user_ids = [user_id for user_id, _ in keys]
    async with engine.connect() as connection:
        existing_rows = (
            await connection.execute(
                select(warnings.c.telegram_user_id, warnings.c.telegram_chat_id).where(
                    warnings.c.telegram_user_id.in_(user_ids)
                )
            )
        ).all()
    existing = {(int(user_id), int(chat_id)) for user_id, chat_id in existing_rows}
    values = [
        {
            "telegram_user_id": row.telegram_user_id,
            "telegram_chat_id": row.telegram_chat_id,
            "username": row.username,
            "warning_count": row.warning_count,
            "last_reason": row.last_reason,
            "last_warning": row.last_warning,
            "banned": row.banned,
        }
        for row in batch
    ]
    statement = insert(warnings).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=[warnings.c.telegram_user_id, warnings.c.telegram_chat_id],
        set_={
            "username": statement.excluded.username,
            "warning_count": statement.excluded.warning_count,
            "last_reason": statement.excluded.last_reason,
            "last_warning": statement.excluded.last_warning,
            "banned": statement.excluded.banned,
        },
    )
    async with engine.begin() as connection:
        await connection.execute(statement)
    updated = sum(1 for key in keys if key in existing)
    return len(batch) - updated, updated


async def run(args: argparse.Namespace) -> dict[str, int | str]:
    if args.batch_size < 1 or args.batch_size > 10_000:
        raise ValueError("--batch-size must be between 1 and 10000")
    source_timezone = timezone_from_name(args.source_timezone)
    database_url = args.database_url or os.getenv("DATABASE_URL")
    if args.apply and not database_url:
        raise ValueError("--apply requires --database-url or DATABASE_URL")

    counts: dict[str, int | str] = {
        "mode": "apply" if args.apply else "dry-run",
        "scanned": 0,
        "valid": 0,
        "imported": 0,
        "updated": 0,
        "collapsed": 0,
        "rejected": 0,
        "would_import": 0,
    }
    rejected: list[RejectedRow] = []
    chosen: dict[tuple[int, int], WarningRow] = {}

    for source in iter_warning_rows(args):
        if not any(cell.strip() for cell in source.values):
            continue
        counts["scanned"] = int(counts["scanned"]) + 1
        try:
            warning = validate_warning_row(source, source_timezone)
        except ValueError as exc:
            if str(exc) == "empty row":
                counts["scanned"] = int(counts["scanned"]) - 1
                continue
            counts["rejected"] = int(counts["rejected"]) + 1
            rejected.append(RejectedRow(source.row_number, str(exc), source.values[:7]))
            continue
        key = (warning.telegram_user_id, warning.telegram_chat_id)
        current = chosen.get(key)
        if current is None:
            chosen[key] = warning
            counts["valid"] = int(counts["valid"]) + 1
            continue
        kept = prefer_warning(current, warning)
        loser = current if kept is warning else warning
        chosen[key] = kept
        counts["collapsed"] = int(counts["collapsed"]) + 1
        rejected.append(
            RejectedRow(
                loser.row_number,
                "same user and chat with a lower warning_count; the higher count is kept",
                (
                    str(loser.telegram_user_id),
                    str(loser.telegram_chat_id),
                    loser.username,
                    str(loser.warning_count),
                    loser.last_reason,
                    loser.last_warning.isoformat(),
                    "TRUE" if loser.banned else "FALSE",
                ),
            )
        )

    validated = list(chosen.values())
    write_rejected_rows(args.rejects_file, rejected)
    if int(counts["scanned"]) != (
        int(counts["valid"]) + int(counts["collapsed"]) + int(counts["rejected"])
    ):
        raise RuntimeError("internal accounting invariant failed")
    if not args.apply:
        counts["would_import"] = int(counts["valid"])
        return counts

    engine = create_async_engine(async_database_url(database_url), pool_pre_ping=True)
    try:
        for start in range(0, len(validated), args.batch_size):
            imported, updated = await upsert_batch(
                engine, validated[start : start + args.batch_size]
            )
            counts["imported"] = int(counts["imported"]) + imported
            counts["updated"] = int(counts["updated"]) + updated
    finally:
        await engine.dispose()
    if int(counts["valid"]) != int(counts["imported"]) + int(counts["updated"]):
        raise RuntimeError("applied accounting invariant failed")
    return counts


def main() -> int:
    try:
        summary = asyncio.run(run(parse_args()))
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({"status": "ok", **summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
