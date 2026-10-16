#!/usr/bin/env python3
"""Exercise every local Postgres table the bot reads.

No model calls and no YouTube calls. One hundred fake student ids are
created, updated, logged, and then deleted. The copied catalog and the
real student and warning rows are left in place.

A failure still runs the cleanup. The last line is one JSON object.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from telegram_bot.domain.interactions import InteractionEvent
from telegram_bot.infrastructure.database import Database
from telegram_bot.infrastructure.postgres_content_items import content_items
from telegram_bot.infrastructure.postgres_folders import folders
from telegram_bot.infrastructure.postgres_interaction_repository import (
    PostgresInteractionRepository,
    interaction_events,
)
from telegram_bot.infrastructure.postgres_note_repository import PostgresNoteRepository
from telegram_bot.infrastructure.postgres_students import students
from telegram_bot.infrastructure.postgres_warnings import warnings
from telegram_bot.services.note_service import NoteService
from telegram_bot.services.postgres_user_service import PostgresUserService
from telegram_bot.services.postgres_warning_service import PostgresWarningService

FAKE_BASE = 9_000_000_001_000
FAKE_COUNT = 100
CLASSES = (10, 11, 12)
SUBJECTS = ("AI", "CS", "IT", "IP")
REMOVED_PATHS = (
    "Class 12/AI/Notes/Unit 1 Capstone Project",
    "Class 12/AI/Notes/Unit 1 Communication Skills-IV",
    "Class 12/AI/Notes/Unit 2 Model Lifecycle",
    "Class 12/AI/Notes/Unit 3 Storytelling Through Data",
)
EXPECTED_COUNTS = {
    "content_items": 222,
    "folders": 93,
    "warnings": 163,
    "students": 1898,
}


@dataclass
class Failure:
    check: str
    detail: str


def parse_class(level: str) -> int | None:
    prefix = "Class "
    if not level.startswith(prefix) or not level[len(prefix) :].isdigit():
        return None
    return int(level[len(prefix) :])


async def table_count(connection, table) -> int:
    value = await connection.scalar(select(func.count()).select_from(table))
    return int(value or 0)


async def cleanup(database: Database) -> None:
    low = FAKE_BASE
    high = FAKE_BASE + FAKE_COUNT
    async with database.engine.begin() as connection:
        await connection.execute(
            delete(interaction_events).where(
                interaction_events.c.telegram_user_id >= low,
                interaction_events.c.telegram_user_id < high,
            )
        )
        await connection.execute(
            delete(warnings).where(
                warnings.c.telegram_user_id >= low,
                warnings.c.telegram_user_id < high,
            )
        )
        await connection.execute(
            delete(students).where(
                students.c.telegram_user_id >= low,
                students.c.telegram_user_id < high,
            )
        )


async def run() -> dict:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set")
    database = Database(database_url)
    failures: list[Failure] = []
    counts = {
        "folders_checked": 0,
        "files_checked": 0,
        "students_checked": 0,
        "warnings_checked": 0,
        "log_rows_checked": 0,
    }
    try:
        await _exercise(database, failures, counts)
    finally:
        await cleanup(database)
        async with database.engine.connect() as connection:
            leftover = await connection.scalar(
                select(func.count())
                .select_from(students)
                .where(
                    students.c.telegram_user_id >= FAKE_BASE,
                    students.c.telegram_user_id < FAKE_BASE + FAKE_COUNT,
                )
            )
            after = {
                "content_items": await table_count(connection, content_items),
                "folders": await table_count(connection, folders),
                "warnings": await table_count(connection, warnings),
                "students": await table_count(connection, students),
            }
        await database.close()
    if leftover:
        failures.append(Failure("cleanup", f"{leftover} fake students remained"))
    for name, expected in EXPECTED_COUNTS.items():
        if after[name] != expected:
            failures.append(
                Failure("restored_count", f"{name} is {after[name]}, expected {expected}")
            )
    return {
        "status": "ok" if not failures else "failed",
        "failed": len(failures),
        "failures": [{"check": item.check, "detail": item.detail} for item in failures[:20]],
        **counts,
    }


async def _exercise(database: Database, failures: list[Failure], counts: dict) -> None:
    async with database.engine.connect() as connection:
        existing = await connection.scalar(
            select(func.count())
            .select_from(students)
            .where(
                students.c.telegram_user_id >= FAKE_BASE,
                students.c.telegram_user_id < FAKE_BASE + FAKE_COUNT,
            )
        )
        if existing:
            raise RuntimeError(f"{existing} fake student ids already exist; cleanup first")
        for name, table in (
            ("content_items", content_items),
            ("folders", folders),
            ("warnings", warnings),
            ("students", students),
        ):
            actual = await table_count(connection, table)
            if actual != EXPECTED_COUNTS[name]:
                failures.append(
                    Failure("starting_count", f"{name} is {actual}, expected {EXPECTED_COUNTS[name]}")
                )
        folder_rows = (
            await connection.execute(select(folders.c.path, folders.c.url, folders.c.drive_folder_id))
        ).all()
        file_rows = (
            await connection.execute(
                select(
                    content_items.c.title,
                    content_items.c.level,
                    content_items.c.subject,
                    content_items.c.resource_type,
                    content_items.c.topic,
                )
            )
        ).all()

    notes = NoteService(PostgresNoteRepository(database))
    paths = {row.path: row for row in folder_rows}
    class_12_ai = paths.get("Class 12/AI/Notes")
    if class_12_ai is None or class_12_ai.drive_folder_id != "129Kuy43zVF-eeDATsmGEi7xailM0FW7M":
        failures.append(Failure("class_12_ai_notes", "the folder from the dev reply is missing"))
    for path in ("Class 10/AI/Notes/2026", "Class 10/AI/Notes/2027"):
        if path not in paths:
            failures.append(Failure("new_year_folder", f"{path} is missing"))
    for path in REMOVED_PATHS:
        if path in paths:
            failures.append(Failure("removed_folder", f"{path} is still present"))

    for row in folder_rows:
        parts = row.path.split("/")
        if len(parts) < 3:
            continue
        class_num = parse_class(parts[0])
        if class_num not in CLASSES or parts[1] not in SUBJECTS:
            failures.append(Failure("folder_shape", row.path))
            continue
        topic = parts[3] if len(parts) >= 4 else None
        url = await notes.get_folder_link(class_num, parts[1], parts[2], topic)
        counts["folders_checked"] += 1
        if url != row.url:
            failures.append(Failure("folder_lookup", f"{row.path} returned {url}"))

    bare = await notes.get_folder_link(10, "AI", "Notes")
    if paths.get("Class 10/AI/Notes") and bare != paths["Class 10/AI/Notes"].url:
        failures.append(Failure("shortest_folder", "Class 10 AI Notes did not use the shortest path"))

    for row in file_rows:
        class_num = parse_class(row.level)
        if class_num is None:
            failures.append(Failure("file_level", row.title))
            continue
        found = await notes.get_notes(
            class_num,
            row.subject,
            row.resource_type,
            row.topic or None,
        )
        counts["files_checked"] += 1
        if not any(note.title == row.title for note in found):
            failures.append(
                Failure(
                    "file_lookup",
                    f"{row.level}/{row.subject}/{row.resource_type}/{row.topic}: {row.title}",
                )
            )

    users = PostgresUserService(database)
    for offset in range(FAKE_COUNT):
        user_id = FAKE_BASE + offset
        created = await users.get_user_profile(user_id, username=f"fake{offset}")
        counts["students_checked"] += 1
        if created.get("current_class") is not None or created.get("preferred_subject") is not None:
            failures.append(Failure("new_student", f"{user_id} was not blank"))
            continue
        if offset == 0:
            await users.update_user_profile(
                user_id,
                {"current_class": 10, "preferred_subject": "AI", "class_updated_year": 2025},
            )
            promoted = await PostgresUserService(database).get_user_profile(user_id)
            if promoted.get("current_class") != 11 or promoted.get("class_updated_year") != 2026:
                failures.append(Failure("promotion", f"class 10 from 2025 became {promoted}"))
            continue
        if offset == 1:
            await users.update_user_profile(
                user_id,
                {"current_class": 12, "preferred_subject": "CS", "class_updated_year": 2025},
            )
            stayed = await PostgresUserService(database).get_user_profile(user_id)
            if stayed.get("current_class") != 12:
                failures.append(Failure("no_promotion_past_12", str(stayed)))
            continue
        if offset == 2:
            await users.update_user_profile(
                user_id,
                {"current_class": 11, "preferred_subject": "AI", "class_updated_year": 2026},
            )
            try:
                await PostgresUserService(database).update_user_profile(user_id, {"current_class": 9})
            except IntegrityError:
                pass
            else:
                failures.append(Failure("reject_class_9", "class 9 was stored"))
            try:
                await PostgresUserService(database).update_user_profile(
                    user_id, {"preferred_subject": "Math"}
                )
            except IntegrityError:
                pass
            else:
                failures.append(Failure("reject_subject_math", "subject Math was stored"))
            kept = await PostgresUserService(database).get_user_profile(user_id)
            if kept.get("current_class") != 11 or kept.get("preferred_subject") != "AI":
                failures.append(Failure("rejected_write_unchanged", str(kept)))
            continue
        class_num = CLASSES[offset % 3]
        subject = SUBJECTS[offset % 4]
        await users.update_user_profile(
            user_id,
            {
                "current_class": class_num,
                "preferred_subject": subject,
                "class_updated_year": 2026,
            },
        )
        saved = await PostgresUserService(database).get_user_profile(user_id)
        if saved.get("current_class") != class_num or saved.get("preferred_subject") != subject:
            failures.append(Failure("profile_round_trip", f"{user_id} saved {saved}"))

    strikes = PostgresWarningService(database)
    warned_user = FAKE_BASE
    first_chat = -9_000_000_000_001
    second_chat = -9_000_000_000_002
    first = await strikes.add_warning(warned_user, first_chat, username="fake0")
    counts["warnings_checked"] += 1
    if first.warning_count != 1 or first.should_ban:
        failures.append(Failure("first_warning", f"count={first.warning_count} ban={first.should_ban}"))
    second = await strikes.add_warning(warned_user, first_chat, username="fake0")
    counts["warnings_checked"] += 1
    if second.warning_count != 2 or not second.should_ban:
        failures.append(Failure("second_warning", f"count={second.warning_count} ban={second.should_ban}"))
    other = await strikes.add_warning(warned_user, second_chat, username="fake0")
    counts["warnings_checked"] += 1
    if other.warning_count != 1 or other.should_ban:
        failures.append(Failure("other_chat", f"count={other.warning_count} ban={other.should_ban}"))
    banned_here = await PostgresWarningService(database).is_banned(warned_user, first_chat)
    banned_there = await PostgresWarningService(database).is_banned(warned_user, second_chat)
    counts["warnings_checked"] += 1
    if not banned_here or banned_there:
        failures.append(Failure("ban_scope", f"first={banned_here} second={banned_there}"))

    logs = PostgresInteractionRepository(database.engine)
    for offset in range(FAKE_COUNT):
        user_id = FAKE_BASE + offset
        event = InteractionEvent(
            telegram_user_id=user_id,
            user_message=f"exercise {offset}",
            bot_response="exercise reply",
            intent_output="agent",
        )
        inserted = await logs.add(event)
        repeated = await logs.add(event)
        counts["log_rows_checked"] += 1
        if not inserted or repeated:
            failures.append(Failure("log_insert", f"{user_id} inserted={inserted} repeated={repeated}"))


def main() -> int:
    try:
        summary = asyncio.run(run())
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
