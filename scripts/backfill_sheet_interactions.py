#!/usr/bin/env python3
"""Restartable Google Sheets/CSV interaction-log backfill."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from scripts.interaction_log_migration import (
    RejectedRow,
    SourceRow,
    ValidatedRow,
    batched,
    iter_csv_rows,
    load_sheet_rows,
    timezone_from_name,
    validate_row,
    write_rejected_rows,
)
from telegram_bot.infrastructure.database import async_database_url
from telegram_bot.infrastructure.postgres_interaction_repository import (
    interaction_events,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a stable interaction-log snapshot and optionally import it. "
            "Dry-run is the default; only --apply writes PostgreSQL."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", type=Path, help="stable Google Sheets CSV export")
    source.add_argument("--sheet-id", help="read-only Google Sheet ID")
    parser.add_argument("--worksheet", default="Logs")
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument(
        "--source-id",
        required=True,
        help="stable Sheet ID used in source_ref (not a filename)",
    )
    parser.add_argument(
        "--source-timezone",
        required=True,
        help="IANA zone for legacy naive timestamps, for example Asia/Kolkata",
    )
    parser.add_argument("--start-row", type=int, default=2)
    parser.add_argument(
        "--end-row",
        type=int,
        required=True,
        help="inclusive snapshot watermark recorded before dual-write",
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--rejects-file",
        type=Path,
        default=Path("artifacts/interaction-backfill-rejected.csv"),
    )
    parser.add_argument(
        "--database-url",
        help="PostgreSQL URL; defaults to DATABASE_URL and is required with --apply",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform idempotent PostgreSQL inserts (otherwise validate only)",
    )
    return parser.parse_args()


def source_rows(args: argparse.Namespace) -> tuple[bool, Iterator[SourceRow]]:
    if args.csv:
        return iter_csv_rows(args.csv)
    if args.source_id != args.sheet_id:
        raise ValueError("--source-id must equal --sheet-id for direct Sheet reads")
    return load_sheet_rows(
        sheet_id=args.sheet_id,
        worksheet_name=args.worksheet,
        credentials_file=args.credentials_file,
    )


def selected_rows(
    rows: Iterator[SourceRow],
    *,
    start_row: int,
    end_row: int | None,
) -> Iterator[SourceRow]:
    if start_row < 2:
        raise ValueError("--start-row must be at least 2")
    if end_row is not None and end_row < start_row:
        raise ValueError("--end-row must be greater than or equal to --start-row")
    for row in rows:
        if row.row_number < start_row:
            continue
        if end_row is not None and row.row_number > end_row:
            break
        yield row


async def insert_batch(
    engine: AsyncEngine,
    batch: list[ValidatedRow],
) -> tuple[int, int]:
    values = [
        {
            "event_id": row.event.event_id,
            "telegram_update_id": row.event.telegram_update_id,
            "telegram_user_id": row.event.telegram_user_id,
            "occurred_at": row.event.occurred_at,
            "user_message": row.event.user_message,
            "bot_response": row.event.bot_response,
            "screener_output": row.event.screener_output,
            "intent_output": row.event.intent_output,
            "entities_output": row.event.entities_output,
            "source_ref": row.event.source_ref,
            "source_timestamp_raw": row.event.source_timestamp_raw,
            "created_at": row.event.created_at,
        }
        for row in batch
    ]
    statement = (
        insert(interaction_events)
        .values(values)
        .on_conflict_do_nothing()
        .returning(interaction_events.c.event_id)
    )
    async with engine.begin() as connection:
        result = await connection.execute(statement)
        imported = len(result.scalars().all())
    return imported, len(batch) - imported


async def run(args: argparse.Namespace) -> dict[str, int | bool | str]:
    if args.batch_size < 1 or args.batch_size > 10_000:
        raise ValueError("--batch-size must be between 1 and 10000")
    if args.end_row is None:
        raise ValueError("--end-row is required")
    source_timezone = timezone_from_name(args.source_timezone)
    has_event_id, rows = source_rows(args)

    database_url = args.database_url or os.getenv("DATABASE_URL")
    if args.apply and not database_url:
        raise ValueError("--apply requires --database-url or DATABASE_URL")
    counts = {
        "scanned": 0,
        "valid": 0,
        "imported": 0,
        "skipped": 0,
        "rejected": 0,
        "would_import": 0,
    }
    rejected: list[RejectedRow] = []
    validated: list[ValidatedRow] = []

    for source in selected_rows(
        rows,
        start_row=args.start_row,
        end_row=args.end_row,
    ):
        counts["scanned"] += 1
        try:
            valid = validate_row(
                source,
                source_id=args.source_id,
                source_timezone=source_timezone,
                has_event_id=has_event_id,
            )
        except ValueError as exc:
            counts["rejected"] += 1
            rejected.append(RejectedRow(source.row_number, str(exc), source.values))
            continue

        counts["valid"] += 1
        validated.append(valid)

    write_rejected_rows(args.rejects_file, rejected)
    if counts["scanned"] != counts["valid"] + counts["rejected"]:
        raise RuntimeError("internal accounting invariant failed")
    expected_rows = args.end_row - args.start_row + 1
    if counts["scanned"] != expected_rows:
        raise RuntimeError(
            f"snapshot is incomplete: expected {expected_rows} selected rows, "
            f"found {counts['scanned']}"
        )
    if not args.apply:
        counts["would_import"] = len(validated)
    else:
        engine = create_async_engine(
            async_database_url(database_url),
            pool_pre_ping=True,
        )
        try:
            for batch in batched(validated, args.batch_size):
                imported, skipped = await insert_batch(engine, batch)
                counts["imported"] += imported
                counts["skipped"] += skipped
        finally:
            await engine.dispose()
    if args.apply and counts["scanned"] != (
        counts["imported"] + counts["skipped"] + counts["rejected"]
    ):
        raise RuntimeError("applied accounting invariant failed")

    return {
        "mode": "apply" if args.apply else "dry-run",
        "source_has_event_id": has_event_id,
        **counts,
    }


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
