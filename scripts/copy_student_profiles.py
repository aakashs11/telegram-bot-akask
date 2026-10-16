#!/usr/bin/env python3
"""Copy UserProfiles into the students table.

Dry-run is the default. It reads a CSV export or the live worksheet and writes
nothing to Postgres. --apply upserts by telegram_user_id, so a second run
updates the same students instead of inserting them again.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

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
from telegram_bot.infrastructure.postgres_students import students

PROFILE_HEADERS = (
    "user_id",
    "username",
    "current_class",
    "preferred_subject",
    "created_at",
    "last_updated",
    "class_updated_year",
)
ALLOWED_CLASSES = {10, 11, 12}
ALLOWED_SUBJECTS = {"AI", "CS", "IT", "IP"}


@dataclass(frozen=True, slots=True)
class StudentProfile:
    """One validated UserProfiles row, ready for the students table."""

    row_number: int
    telegram_user_id: int
    username: str
    current_class: int | None
    preferred_subject: str | None
    created_at: datetime
    last_updated: datetime
    class_updated_year: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate UserProfiles and optionally upsert them into students. "
            "Dry-run is the default; only --apply writes PostgreSQL."
        )
    )
    parser.add_argument("--csv", type=Path, help="UserProfiles CSV export")
    parser.add_argument(
        "--sheet-id",
        help="Google Sheet ID. Defaults to SHEET_ID when --csv is omitted",
    )
    parser.add_argument("--worksheet", default="UserProfiles")
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument(
        "--source-timezone",
        required=True,
        help="IANA zone for timestamps that have no offset, for example Asia/Kolkata",
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--rejects-file",
        type=Path,
        default=Path("artifacts/student-profile-rejected.csv"),
    )
    parser.add_argument("--database-url")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="upsert into PostgreSQL (otherwise validate only)",
    )
    return parser.parse_args()


def validate_profile_headers(headers: tuple[str, ...]) -> None:
    """Require the seven UserProfiles columns, in order. Extra columns are ignored."""
    normalized = tuple(value.strip().lstrip("\ufeff") for value in headers)
    if normalized[:7] != PROFILE_HEADERS:
        raise ValueError(
            "source headers must begin with exactly: " + ", ".join(PROFILE_HEADERS)
        )


def iter_profile_csv(path: Path) -> Iterator[SourceRow]:
    """Stream a CSV export. Row 1 is the header. Data starts at row 2."""
    handle = path.open("r", encoding="utf-8-sig", newline="")
    reader = csv.reader(handle)
    try:
        headers = tuple(next(reader))
        validate_profile_headers(headers)
    except Exception:
        handle.close()
        raise

    def rows() -> Iterator[SourceRow]:
        try:
            width = max(len(headers), 7)
            for row_number, row in enumerate(reader, start=2):
                cells = tuple(row)
                if len(cells) < width:
                    cells += ("",) * (width - len(cells))
                yield SourceRow(row_number, cells[:width])
        finally:
            handle.close()

    return rows()


def iter_profile_sheet(
    *,
    sheet_id: str,
    worksheet_name: str,
    credentials_file: Path | None,
) -> Iterator[SourceRow]:
    """Read the worksheet once. This does not update any cells.

    Local runs use service_account.json, the same file the dev bot uses.
    Cloud Run has no such file and falls back to Application Default Credentials.
    """
    import gspread

    path = credentials_file or Path("service_account.json")
    if path.is_file():
        client = gspread.service_account(filename=str(path))
    else:
        import google.auth

        try:
            credentials, _ = google.auth.default()
        except Exception as exc:
            raise ValueError(
                "No service_account.json in this directory, and Google "
                "Application Default Credentials are not set. Pass "
                "--credentials-file with the bot's service account JSON."
            ) from exc
        client = gspread.authorize(credentials)
    values = client.open_by_key(sheet_id).worksheet(worksheet_name).get_all_values()
    if not values:
        raise ValueError("source worksheet is empty")
    headers = tuple(str(value) for value in values[0])
    validate_profile_headers(headers)
    width = max(len(headers), 7)

    def rows() -> Iterator[SourceRow]:
        for row_number, row in enumerate(values[1:], start=2):
            cells = tuple(str(value) for value in row)
            if len(cells) < width:
                cells += ("",) * (width - len(cells))
            yield SourceRow(row_number, cells[:width])

    return rows()


def _blank_to_none(value: str) -> str | None:
    text = value.strip()
    return text or None


def validate_profile_row(
    source: SourceRow,
    *,
    source_timezone: ZoneInfo,
) -> StudentProfile:
    """Turn one sheet row into a student, or raise ValueError with the reason."""
    if len(source.values) < 7:
        raise ValueError(f"expected at least 7 columns, found {len(source.values)}")
    user_id_raw, username_raw, class_raw, subject_raw, created_raw, updated_raw, year_raw = (
        source.values[:7]
    )
    if not any(cell.strip() for cell in source.values):
        raise ValueError("empty row")

    try:
        telegram_user_id = int(user_id_raw.strip())
    except ValueError as exc:
        raise ValueError("user_id must be an integer") from exc
    if telegram_user_id <= 0:
        raise ValueError("user_id must be a positive Telegram user id")

    class_text = _blank_to_none(class_raw)
    if class_text is None:
        current_class = None
    else:
        try:
            current_class = int(class_text)
        except ValueError as exc:
            raise ValueError("current_class must be 10, 11, 12, or blank") from exc
        if current_class not in ALLOWED_CLASSES:
            raise ValueError("current_class must be 10, 11, 12, or blank")

    subject = _blank_to_none(subject_raw)
    if subject is not None and subject not in ALLOWED_SUBJECTS:
        raise ValueError("preferred_subject must be AI, CS, IT, IP, or blank")

    try:
        created_at = parse_source_timestamp(created_raw, source_timezone)
        last_updated = parse_source_timestamp(updated_raw, source_timezone)
    except ValueError as exc:
        raise ValueError(f"profile timestamp: {exc}") from exc

    year_text = _blank_to_none(year_raw)
    if year_text is None:
        class_updated_year = 0
    else:
        try:
            class_updated_year = int(year_text)
        except ValueError as exc:
            raise ValueError("class_updated_year must be a whole number or blank") from exc

    return StudentProfile(
        row_number=source.row_number,
        telegram_user_id=telegram_user_id,
        username=username_raw.strip(),
        current_class=current_class,
        preferred_subject=subject,
        created_at=created_at,
        last_updated=last_updated,
        class_updated_year=class_updated_year,
    )


async def upsert_batch(engine: AsyncEngine, batch: list[StudentProfile]) -> tuple[int, int]:
    """Insert new students and update rows that already use the same Telegram id."""
    ids = [profile.telegram_user_id for profile in batch]
    async with engine.connect() as connection:
        existing = set(
            (
                await connection.execute(
                    select(students.c.telegram_user_id).where(
                        students.c.telegram_user_id.in_(ids)
                    )
                )
            ).scalars().all()
        )
    values = [
        {
            "telegram_user_id": profile.telegram_user_id,
            "username": profile.username,
            "current_class": profile.current_class,
            "preferred_subject": profile.preferred_subject,
            "created_at": profile.created_at,
            "last_updated": profile.last_updated,
            "class_updated_year": profile.class_updated_year,
        }
        for profile in batch
    ]
    statement = insert(students).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=[students.c.telegram_user_id],
        set_={
            "username": statement.excluded.username,
            "current_class": statement.excluded.current_class,
            "preferred_subject": statement.excluded.preferred_subject,
            "created_at": statement.excluded.created_at,
            "last_updated": statement.excluded.last_updated,
            "class_updated_year": statement.excluded.class_updated_year,
        },
    )
    async with engine.begin() as connection:
        await connection.execute(statement)
    updated = len(existing)
    return len(batch) - updated, updated


async def run(args: argparse.Namespace) -> dict[str, int | str]:
    if args.batch_size < 1 or args.batch_size > 10_000:
        raise ValueError("--batch-size must be between 1 and 10000")
    if args.csv and args.sheet_id:
        raise ValueError("pass either --csv or --sheet-id, not both")
    sheet_id = args.sheet_id or (None if args.csv else os.getenv("SHEET_ID"))
    if args.csv:
        rows = iter_profile_csv(args.csv)
    else:
        if not sheet_id:
            raise ValueError("pass --csv or --sheet-id, or set SHEET_ID")
        rows = iter_profile_sheet(
            sheet_id=sheet_id,
            worksheet_name=args.worksheet,
            credentials_file=args.credentials_file,
        )

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
        "rejected": 0,
        "would_import": 0,
    }
    rejected: list[RejectedRow] = []
    validated: list[StudentProfile] = []
    seen_ids: set[int] = set()

    for source in rows:
        if not any(cell.strip() for cell in source.values):
            continue
        counts["scanned"] = int(counts["scanned"]) + 1
        try:
            profile = validate_profile_row(source, source_timezone=source_timezone)
        except ValueError as exc:
            if str(exc) == "empty row":
                counts["scanned"] = int(counts["scanned"]) - 1
                continue
            counts["rejected"] = int(counts["rejected"]) + 1
            rejected.append(RejectedRow(source.row_number, str(exc), source.values[:7]))
            continue
        if profile.telegram_user_id in seen_ids:
            counts["rejected"] = int(counts["rejected"]) + 1
            rejected.append(
                RejectedRow(
                    source.row_number,
                    "duplicate user_id; the first row is kept",
                    source.values[:7],
                )
            )
            continue
        seen_ids.add(profile.telegram_user_id)
        counts["valid"] = int(counts["valid"]) + 1
        validated.append(profile)

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
