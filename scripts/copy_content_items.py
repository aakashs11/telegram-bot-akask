#!/usr/bin/env python3
"""Copy the Index sheet into content_items.

Dry-run is the default. --apply upserts on drive_file_id.
The sheet is not modified. File bytes stay in Google Drive.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from scripts.interaction_log_migration import RejectedRow, SourceRow, write_rejected_rows
from telegram_bot.infrastructure.database import async_database_url
from telegram_bot.infrastructure.postgres_content_items import content_items

INDEX_HEADERS = (
    "Title",
    "Link",
    "Level",
    "Subject",
    "Type",
    "Topic",
    "File ID",
)


@dataclass(frozen=True, slots=True)
class ContentItem:
    """One validated Index row."""

    row_number: int
    drive_file_id: str
    title: str
    link: str
    level: str
    subject: str
    resource_type: str
    topic: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the Index sheet and optionally upsert it into content_items. "
            "Dry-run is the default; only --apply writes PostgreSQL."
        )
    )
    parser.add_argument("--csv", type=Path, help="Index CSV export")
    parser.add_argument("--sheet-id", help="Google Sheet ID. Defaults to SHEET_ID")
    parser.add_argument("--worksheet", default="Index")
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--rejects-file",
        type=Path,
        default=Path("artifacts/content-items-rejected.csv"),
    )
    parser.add_argument("--database-url")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def validate_index_headers(headers: tuple[str, ...]) -> None:
    """Require the seven Index columns, in order. Extra columns are ignored."""
    normalized = tuple(value.strip().lstrip("\ufeff") for value in headers)
    if normalized[:7] != INDEX_HEADERS:
        raise ValueError(
            "source headers must begin with exactly: " + ", ".join(INDEX_HEADERS)
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


def iter_index_rows(args: argparse.Namespace) -> Iterator[SourceRow]:
    """Stream Index rows from a CSV or from the live worksheet."""
    if args.csv and args.sheet_id:
        raise ValueError("pass either --csv or --sheet-id, not both")
    if args.csv:
        handle = args.csv.open("r", encoding="utf-8-sig", newline="")
        reader = csv.reader(handle)
        try:
            headers = tuple(next(reader))
            validate_index_headers(headers)
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
    values = (
        _sheet_client(args.credentials_file)
        .open_by_key(sheet_id)
        .worksheet(args.worksheet)
        .get_all_values()
    )
    if not values:
        raise ValueError("source worksheet is empty")
    headers = tuple(str(value) for value in values[0])
    validate_index_headers(headers)
    width = max(len(headers), 7)

    def sheet_rows() -> Iterator[SourceRow]:
        for row_number, row in enumerate(values[1:], start=2):
            cells = tuple(str(value) for value in row)
            if len(cells) < width:
                cells += ("",) * (width - len(cells))
            yield SourceRow(row_number, cells[:width])

    return sheet_rows()


def validate_index_row(source: SourceRow) -> ContentItem:
    """Turn one Index row into a catalog item, or raise ValueError."""
    if len(source.values) < 7:
        raise ValueError(f"expected at least 7 columns, found {len(source.values)}")
    title, link, level, subject, resource_type, topic, file_id = (
        cell.strip() for cell in source.values[:7]
    )
    if not any((title, link, level, subject, resource_type, topic, file_id)):
        raise ValueError("empty row")
    if not file_id:
        raise ValueError("File ID is empty")
    if not title:
        raise ValueError("Title is empty")
    return ContentItem(
        row_number=source.row_number,
        drive_file_id=file_id,
        title=title,
        link=link,
        level=level,
        subject=subject,
        resource_type=resource_type,
        topic=topic,
    )


async def upsert_batch(engine: AsyncEngine, batch: list[ContentItem]) -> tuple[int, int]:
    ids = [item.drive_file_id for item in batch]
    async with engine.connect() as connection:
        existing = set(
            (
                await connection.execute(
                    select(content_items.c.drive_file_id).where(
                        content_items.c.drive_file_id.in_(ids)
                    )
                )
            ).scalars().all()
        )
    values = [
        {
            "drive_file_id": item.drive_file_id,
            "title": item.title,
            "link": item.link,
            "level": item.level,
            "subject": item.subject,
            "resource_type": item.resource_type,
            "topic": item.topic,
        }
        for item in batch
    ]
    statement = insert(content_items).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=[content_items.c.drive_file_id],
        set_={
            "title": statement.excluded.title,
            "link": statement.excluded.link,
            "level": statement.excluded.level,
            "subject": statement.excluded.subject,
            "resource_type": statement.excluded.resource_type,
            "topic": statement.excluded.topic,
        },
    )
    async with engine.begin() as connection:
        await connection.execute(statement)
    updated = len(existing)
    return len(batch) - updated, updated


async def run(args: argparse.Namespace) -> dict[str, int | str]:
    if args.batch_size < 1 or args.batch_size > 10_000:
        raise ValueError("--batch-size must be between 1 and 10000")
    database_url = args.database_url or os.getenv("DATABASE_URL")
    if args.apply and not database_url:
        raise ValueError("--apply requires --database-url or DATABASE_URL")

    counts: dict[str, int | str] = {
        "mode": "apply" if args.apply else "dry-run",
        "scanned": 0,
        "valid": 0,
        "imported": 0,
        "updated": 0,
        "rejected": 0,
        "would_import": 0,
    }
    rejected: list[RejectedRow] = []
    validated: list[ContentItem] = []
    seen_ids: set[str] = set()

    for source in iter_index_rows(args):
        if not any(cell.strip() for cell in source.values):
            continue
        counts["scanned"] = int(counts["scanned"]) + 1
        try:
            item = validate_index_row(source)
        except ValueError as exc:
            if str(exc) == "empty row":
                counts["scanned"] = int(counts["scanned"]) - 1
                continue
            counts["rejected"] = int(counts["rejected"]) + 1
            rejected.append(RejectedRow(source.row_number, str(exc), source.values[:7]))
            continue
        if item.drive_file_id in seen_ids:
            counts["rejected"] = int(counts["rejected"]) + 1
            rejected.append(
                RejectedRow(
                    source.row_number,
                    "duplicate File ID; the first row is kept",
                    source.values[:7],
                )
            )
            continue
        seen_ids.add(item.drive_file_id)
        counts["valid"] = int(counts["valid"]) + 1
        validated.append(item)

    write_rejected_rows(args.rejects_file, rejected)
    if int(counts["scanned"]) != int(counts["valid"]) + int(counts["rejected"]):
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
