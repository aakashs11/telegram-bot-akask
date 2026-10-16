#!/usr/bin/env python3
"""Refresh content_items and folders from Google Drive.

Dry-run is the default. It lists Drive and prints counts. --apply replaces
both tables in one transaction. The Index and Folders sheets are not modified.
An empty Drive listing is refused, because a failed API call returns no files.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_bot.infrastructure.database import Database
from telegram_bot.services.catalog_sync import replace_content_catalog
from telegram_bot.services.drive_service import DriveService
from telegram_bot.services.sync_service import SyncService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "List Drive and optionally replace content_items and folders. "
            "Dry-run is the default; only --apply writes PostgreSQL."
        )
    )
    parser.add_argument("--database-url")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def summary_from_snapshot(snapshot, mode: str) -> dict[str, int | str]:
    return {
        "mode": mode,
        "files": len(snapshot.items),
        "folders": len(snapshot.folders),
        "skipped": snapshot.skipped,
        "duplicate_file_ids": snapshot.duplicate_file_ids,
        "duplicate_folder_ids": snapshot.duplicate_folder_ids,
        "duplicate_paths": snapshot.duplicate_paths,
    }


async def run(args: argparse.Namespace) -> dict[str, int | str]:
    database_url = args.database_url or os.getenv("DATABASE_URL")
    if args.apply and not database_url:
        raise ValueError("--apply requires --database-url or DATABASE_URL")
    snapshot = SyncService(DriveService()).build_snapshot()
    if not args.apply:
        return summary_from_snapshot(snapshot, "dry-run")
    database = Database(database_url)
    try:
        await replace_content_catalog(database, snapshot)
    finally:
        await database.close()
    return summary_from_snapshot(snapshot, "apply")


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
