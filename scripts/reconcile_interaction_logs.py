#!/usr/bin/env python3
"""Read-only payload reconciliation for historical and dual-written events."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
from collections.abc import Iterator, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from scripts.interaction_log_migration import (
    PAYLOAD_HEADERS,
    RejectedRow,
    SourceRow,
    ValidatedRow,
    field_hashes,
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

SINK_LOG_PATTERN = re.compile(
    r"interaction_sink_write .*sink=postgres success=(?P<success>True|False) "
    r"inserted=.* latency_ms=(?P<latency>[0-9.]+)"
)
T = TypeVar("T")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only reconciliation of a stable Sheet snapshot and PostgreSQL."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", type=Path)
    source.add_argument("--sheet-id")
    parser.add_argument("--worksheet", default="Logs")
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-timezone", required=True)
    parser.add_argument(
        "--historical-end-row",
        required=True,
        type=int,
        help="inclusive pre-dual-write row watermark",
    )
    parser.add_argument(
        "--dual-start",
        required=True,
        help="inclusive timezone-aware ISO timestamp for the dual-write window",
    )
    parser.add_argument(
        "--dual-end",
        required=True,
        help="exclusive timezone-aware ISO timestamp for the dual-write window",
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--database-url", help="defaults to DATABASE_URL")
    parser.add_argument(
        "--rejects-file",
        type=Path,
        default=Path("artifacts/interaction-reconcile-rejected.csv"),
    )
    parser.add_argument(
        "--report-file",
        type=Path,
        default=Path("artifacts/interaction-reconciliation.json"),
    )
    parser.add_argument(
        "--application-log",
        type=Path,
        action="append",
        default=[],
        required=True,
        help="bot log file for the same dual-write window; may be repeated",
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


def chunks(items: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    for offset in range(0, len(items), size):
        yield items[offset : offset + size]


async def fetch_by_source_refs(
    engine: AsyncEngine,
    source_refs: Sequence[str],
    batch_size: int,
) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    columns = tuple(interaction_events.c)
    async with engine.connect() as connection:
        for batch in chunks(source_refs, batch_size):
            result = await connection.execute(
                select(*columns).where(interaction_events.c.source_ref.in_(batch))
            )
            for row in result.mappings():
                found[row["source_ref"]] = dict(row)
    return found


async def fetch_by_event_ids(
    engine: AsyncEngine,
    event_ids: Sequence[UUID],
    batch_size: int,
) -> dict[UUID, dict[str, Any]]:
    found: dict[UUID, dict[str, Any]] = {}
    columns = tuple(interaction_events.c)
    async with engine.connect() as connection:
        for batch in chunks(event_ids, batch_size):
            result = await connection.execute(
                select(*columns).where(interaction_events.c.event_id.in_(batch))
            )
            for row in result.mappings():
                found[row["event_id"]] = dict(row)
    return found


async def fetch_runtime_event_ids_between(
    engine: AsyncEngine,
    start: datetime,
    end: datetime,
) -> set[UUID]:
    async with engine.connect() as connection:
        result = await connection.execute(
            select(interaction_events.c.event_id).where(
                interaction_events.c.source_ref.is_(None),
                interaction_events.c.occurred_at >= start,
                interaction_events.c.occurred_at < end,
            )
        )
        return set(result.scalars().all())


def parse_window_timestamp(value: str, option: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{option} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{option} must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def database_payload(row: dict[str, Any]) -> tuple[str, ...]:
    timestamp = row["source_timestamp_raw"]
    if timestamp is None:
        timestamp = row["occurred_at"].isoformat()
    return (
        timestamp,
        str(row["telegram_user_id"]),
        row["user_message"],
        row["bot_response"],
        row["screener_output"],
        row["intent_output"],
        row["entities_output"],
    )


def mismatched_fields(
    source_payload: Sequence[str],
    database_row: dict[str, Any],
    *,
    source_timezone: Any,
) -> list[str]:
    expected = field_hashes(source_payload, source_timezone=source_timezone)
    actual = field_hashes(
        database_payload(database_row),
        source_timezone=source_timezone,
    )
    return [
        PAYLOAD_HEADERS[index]
        for index, (left, right) in enumerate(zip(expected, actual))
        if left != right
    ]


def percentile(values: Sequence[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return round(ordered[index], 2)


def summarize_application_logs(paths: Sequence[Path]) -> dict[str, Any]:
    latencies: list[float] = []
    failures = 0
    for path in paths:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                match = SINK_LOG_PATTERN.search(line)
                if not match:
                    continue
                latencies.append(float(match.group("latency")))
                failures += match.group("success") == "False"
    return {
        "files_supplied": len(paths),
        "postgres_writes_observed": len(latencies),
        "postgres_write_failures": failures,
        "latency_ms_p50": percentile(latencies, 0.50),
        "latency_ms_p95": percentile(latencies, 0.95),
        "latency_ms_max": round(max(latencies), 2) if latencies else None,
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.historical_end_row < 1:
        raise ValueError("--historical-end-row must be positive")
    if args.batch_size < 1 or args.batch_size > 10_000:
        raise ValueError("--batch-size must be between 1 and 10000")
    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("--database-url or DATABASE_URL is required")

    source_timezone = timezone_from_name(args.source_timezone)
    dual_start = parse_window_timestamp(args.dual_start, "--dual-start")
    dual_end = parse_window_timestamp(args.dual_end, "--dual-end")
    if dual_end <= dual_start:
        raise ValueError("--dual-end must be later than --dual-start")
    has_event_id, rows = source_rows(args)
    historical: list[ValidatedRow] = []
    dual: list[ValidatedRow] = []
    rejected: list[RejectedRow] = []
    dual_missing_event_id = 0

    for source in rows:
        try:
            row = validate_row(
                source,
                source_id=args.source_id,
                source_timezone=source_timezone,
                has_event_id=has_event_id,
            )
        except ValueError as exc:
            rejected.append(RejectedRow(source.row_number, str(exc), source.values))
            continue
        if source.row_number <= args.historical_end_row:
            historical.append(row)
        elif row.event_id_from_sheet is None:
            dual_missing_event_id += 1
        else:
            dual.append(row)

    engine = create_async_engine(
        async_database_url(database_url),
        pool_pre_ping=True,
    )
    try:
        by_source_ref = await fetch_by_source_refs(
            engine,
            [row.event.source_ref for row in historical if row.event.source_ref],
            args.batch_size,
        )
        by_event_id = await fetch_by_event_ids(
            engine,
            [
                row.event_id_from_sheet
                for row in dual
                if row.event_id_from_sheet is not None
            ],
            args.batch_size,
        )
        database_window_event_ids = await fetch_runtime_event_ids_between(
            engine,
            dual_start,
            dual_end,
        )
    finally:
        await engine.dispose()

    historical_missing: list[str] = []
    historical_mismatches: list[dict[str, Any]] = []
    raw_timestamp_mismatches = 0
    for row in historical:
        database_row = by_source_ref.get(row.event.source_ref or "")
        if database_row is None:
            historical_missing.append(row.event.source_ref or "")
            continue
        fields = mismatched_fields(
            row.payload,
            database_row,
            source_timezone=source_timezone,
        )
        if database_row["source_timestamp_raw"] != row.payload[0]:
            raw_timestamp_mismatches += 1
        if fields:
            historical_mismatches.append(
                {"source_ref": row.event.source_ref, "fields": fields}
            )

    dual_missing: list[str] = []
    dual_mismatches: list[dict[str, Any]] = []
    sheet_window_event_ids: set[UUID] = set()
    duplicate_sheet_event_ids: set[UUID] = set()
    sheet_rows_in_window = 0
    dual_outside_window = 0
    for row in dual:
        event_id = row.event_id_from_sheet
        if not (dual_start <= row.event.occurred_at < dual_end):
            dual_outside_window += 1
            continue
        sheet_rows_in_window += 1
        if event_id:
            if event_id in sheet_window_event_ids:
                duplicate_sheet_event_ids.add(event_id)
            sheet_window_event_ids.add(event_id)
        database_row = by_event_id.get(event_id) if event_id else None
        if database_row is None:
            dual_missing.append(str(event_id))
            continue
        fields = mismatched_fields(
            row.payload,
            database_row,
            source_timezone=source_timezone,
        )
        if fields:
            dual_mismatches.append({"event_id": str(event_id), "fields": fields})
    database_only_event_ids = sorted(
        str(event_id)
        for event_id in database_window_event_ids - sheet_window_event_ids
    )

    write_rejected_rows(args.rejects_file, rejected)
    historical_rejected = sum(
        row.row_number <= args.historical_end_row for row in rejected
    )
    historical_observed = len(historical) + historical_rejected
    historical_expected = args.historical_end_row - 1
    historical_present = len(historical) - len(historical_missing)
    accounting_exact = (
        historical_observed == historical_expected
        and historical_expected == historical_present + historical_rejected
    )
    log_summary = summarize_application_logs(args.application_log)
    passed = (
        accounting_exact
        and not historical_mismatches
        and raw_timestamp_mismatches == 0
        and not dual_missing
        and not dual_mismatches
        and dual_missing_event_id == 0
        and not duplicate_sheet_event_ids
        and dual_outside_window == 0
        and not database_only_event_ids
        and not rejected
        and log_summary["files_supplied"] > 0
        and log_summary["postgres_writes_observed"] > 0
        and log_summary["postgres_write_failures"] == 0
    )
    report = {
        "status": "pass" if passed else "fail",
        "historical": {
            "export_rows_expected": historical_expected,
            "export_rows_observed": historical_observed,
            "database_rows_present": historical_present,
            "explicitly_rejected": historical_rejected,
            "missing": len(historical_missing),
            "payload_hash_mismatches": len(historical_mismatches),
            "raw_timestamp_mismatches": raw_timestamp_mismatches,
            "accounting_exact": accounting_exact,
        },
        "dual_write": {
            "sheet_rows_in_window": sheet_rows_in_window,
            "unique_sheet_event_ids": len(sheet_window_event_ids),
            "duplicate_event_ids_in_sheet": len(duplicate_sheet_event_ids),
            "missing_event_ids_in_sheet": dual_missing_event_id,
            "events_outside_declared_window": dual_outside_window,
            "missing_in_database": len(dual_missing),
            "missing_in_sheet": len(database_only_event_ids),
            "payload_hash_mismatches": len(dual_mismatches),
        },
        "application_logs": log_summary,
        "mismatches": {
            "historical_missing_source_refs": historical_missing,
            "historical_payloads": historical_mismatches,
            "dual_missing_event_ids": dual_missing,
            "dual_database_only_event_ids": database_only_event_ids,
            "dual_duplicate_sheet_event_ids": sorted(
                str(event_id) for event_id in duplicate_sheet_event_ids
            ),
            "dual_payloads": dual_mismatches,
        },
    }
    args.report_file.parent.mkdir(parents=True, exist_ok=True)
    args.report_file.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    try:
        report = asyncio.run(run(parse_args()))
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
