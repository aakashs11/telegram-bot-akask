#!/usr/bin/env python3
"""Copy the Folders sheet into the folders table.

Dry-run is the default. --apply upserts on drive_folder_id.
The sheet is not modified. The folders stay in Google Drive.
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
from telegram_bot.infrastructure.postgres_folders import folders

FOLDER_HEADERS = ("Path", "Folder ID", "URL")


@dataclass(frozen=True, slots=True)
class FolderRow:
    """One validated Folders-sheet row."""

    row_number: int
    drive_folder_id: str
    path: str
    url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the Folders sheet and optionally upsert it. "
            "Dry-run is the default; only --apply writes PostgreSQL."
        )
    )
    parser.add_argument("--csv", type=Path, help="Folders CSV export")
    parser.add_argument("--sheet-id", help="Google Sheet ID. Defaults to SHEET_ID")
    parser.add_argument("--worksheet", default="Folders")
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--rejects-file",
        type=Path,
        default=Path("artifacts/folders-rejected.csv"),
    )
    parser.add_argument("--database-url")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def validate_folder_headers(headers: tuple[str, ...]) -> None:
    """Require Path, Folder ID, and URL, in that order."""
    normalized = tuple(value.strip().lstrip("\ufeff") for value in headers)
    if normalized[:3] != FOLDER_HEADERS:
        raise ValueError(
            "source headers must begin with exactly: " + ", ".join(FOLDER_HEADERS)
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


def iter_folder_rows(args: argparse.Namespace) -> Iterator[SourceRow]:
    """Stream Folders rows from a CSV or from the live worksheet."""
    if args.csv and args.sheet_id:
        raise ValueError("pass either --csv or --sheet-id, not both")
    if args.csv:
        handle = args.csv.open("r", encoding="utf-8-sig", newline="")
        reader = csv.reader(handle)
        try:
            headers = tuple(next(reader))
            validate_folder_headers(headers)
        except Exception:
            handle.close()
            raise

        def csv_rows() -> Iterator[SourceRow]:
            try:
                width = max(len(headers), 3)
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
    validate_folder_headers(headers)
    width = max(len(headers), 3)

    def sheet_rows() -> Iterator[SourceRow]:
        for row_number, row in enumerate(values[1:], start=2):
            cells = tuple(str(value) for value in row)
            if len(cells) < width:
                cells += ("",) * (width - len(cells))
            yield SourceRow(row_number, cells[:width])

    return sheet_rows()


def validate_folder_row(source: SourceRow) -> FolderRow:
    """Turn one Folders row into a folder record, or raise ValueError."""
    if len(source.values) < 3:
        raise ValueError(f"expected at least 3 columns, found {len(source.values)}")
    path, folder_id, url = (cell.strip() for cell in source.values[:3])
    if not any((path, folder_id, url)):
        raise ValueError("empty row")
    if not folder_id:
        raise ValueError("Folder ID is empty")
    if not path:
        raise ValueError("Path is empty")
    return FolderRow(
        row_number=source.row_number,
        drive_folder_id=folder_id,
        path=path,
        url=url,
    )


async def upsert_batch(engine: AsyncEngine, batch: list[FolderRow]) -> tuple[int, int]:
    ids = [row.drive_folder_id for row in batch]
    async with engine.connect() as connection:
        existing = set(
            (
                await connection.execute(
                    select(folders.c.drive_folder_id).where(
                        folders.c.drive_folder_id.in_(ids)
                    )
                )
            ).scalars().all()
        )
    values = [
        {
            "drive_folder_id": row.drive_folder_id,
            "path": row.path,
            "url": row.url,
        }
        for row in batch
    ]
    statement = insert(folders).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=[folders.c.drive_folder_id],
        set_={
            "path": statement.excluded.path,
            "url": statement.excluded.url,
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
    validated: list[FolderRow] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()

    for source in iter_folder_rows(args):
        if not any(cell.strip() for cell in source.values):
            continue
        counts["scanned"] = int(counts["scanned"]) + 1
        try:
            folder = validate_folder_row(source)
        except ValueError as exc:
            if str(exc) == "empty row":
                counts["scanned"] = int(counts["scanned"]) - 1
                continue
            counts["rejected"] = int(counts["rejected"]) + 1
            rejected.append(RejectedRow(source.row_number, str(exc), source.values[:3]))
            continue
        if folder.drive_folder_id in seen_ids:
            counts["rejected"] = int(counts["rejected"]) + 1
            rejected.append(
                RejectedRow(
                    source.row_number,
                    "duplicate Folder ID; the first row is kept",
                    source.values[:3],
                )
            )
            continue
        if folder.path in seen_paths:
            counts["rejected"] = int(counts["rejected"]) + 1
            rejected.append(
                RejectedRow(
                    source.row_number,
                    "duplicate Path; the first row is kept",
                    source.values[:3],
                )
            )
            continue
        seen_ids.add(folder.drive_folder_id)
        seen_paths.add(folder.path)
        counts["valid"] = int(counts["valid"]) + 1
        validated.append(folder)

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
