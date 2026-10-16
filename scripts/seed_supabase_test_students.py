#!/usr/bin/env python3
"""Keep 100 fake students on Supabase and run one message pass.

These are not Telegram accounts. The ids sit far above real Telegram ids.
Private "notes" messages go through ChatRuntime and the Postgres services,
then one interaction row is stored the same way a private reply is logged.
The catalog is only read. Real student, warning, and log rows are counted
before and after and must stay the same.

Run again after the seed exists and it only checks the rows. It does not
add a second warning or a second log. The last line is one JSON object.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from telegram_bot.domain.interactions import InteractionEvent
from telegram_bot.infrastructure.database import Database
from telegram_bot.infrastructure.postgres_content_items import content_items
from telegram_bot.infrastructure.postgres_folders import folders
from telegram_bot.infrastructure.postgres_interaction_repository import (
    PostgresInteractionRepository,
    interaction_events,
)
from telegram_bot.infrastructure.postgres_note_repository import (
    PostgresNoteRepository,
    choose_folder_url,
)
from telegram_bot.infrastructure.postgres_students import students
from telegram_bot.infrastructure.postgres_warnings import warnings
from telegram_bot.runtime.chat_runtime import ChatRuntime
from telegram_bot.runtime.contracts import ChatMessage, ChatType, Platform, ReplyMode
from telegram_bot.services.interaction_logging_service import InteractionLoggingService
from telegram_bot.services.note_service import NoteService
from telegram_bot.services.postgres_user_service import PostgresUserService
from telegram_bot.services.postgres_warning_service import PostgresWarningService

TEST_BASE = 9_100_000_001_000
TEST_COUNT = 100
TEST_CHAT_A = -9_100_000_000_001
TEST_CHAT_B = -9_100_000_000_002
CLASSES = (10, 11, 12)
SUBJECTS = ("AI", "CS", "IT", "IP")
REMOVED_PATHS = (
    "Class 12/AI/Notes/Unit 1 Capstone Project",
    "Class 12/AI/Notes/Unit 1 Communication Skills-IV",
    "Class 12/AI/Notes/Unit 2 Model Lifecycle",
    "Class 12/AI/Notes/Unit 3 Storytelling Through Data",
)


def supabase_url() -> str:
    for line in Path("supabase.env").read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("DATABASE_URL="):
            return stripped.split("=", 1)[1].strip().strip('"')
    raise ValueError("supabase.env has no DATABASE_URL")


def user_id_for(offset: int) -> int:
    return TEST_BASE + offset


def username_for(offset: int) -> str:
    return f"test_seed_{offset:03d}"


def expected_profile(offset: int) -> dict:
    """The row that should remain after the message pass."""
    if offset == 0:
        # Class 10 saved in 2025 is promoted on the next read after 1 June 2026.
        return {"current_class": 11, "preferred_subject": "AI", "class_updated_year": 2026}
    if offset == 1:
        return {"current_class": 12, "preferred_subject": "CS", "class_updated_year": 2025}
    if offset == 2:
        return {"current_class": 11, "preferred_subject": "AI", "class_updated_year": 2026}
    if offset >= 92:
        return {"current_class": None, "preferred_subject": None, "class_updated_year": 2026}
    return {
        "current_class": CLASSES[offset % 3],
        "preferred_subject": SUBJECTS[offset % 4],
        "class_updated_year": 2026,
    }


def in_test_range(column):
    return (column >= TEST_BASE) & (column < TEST_BASE + TEST_COUNT)


def outside_test_range(column):
    return ~in_test_range(column)


class NotesAgent:
    """Stand-in for the model. It only reads the catalog with the saved profile."""

    def __init__(self, notes: NoteService):
        self.notes = notes
        self.seen: list[dict] = []

    async def process(
        self,
        user_message: str,
        user_id: int,
        user_profile: dict,
        user_service,
        chat_type: str,
        is_admin: bool = False,
    ) -> str:
        class_num = user_profile.get("current_class")
        subject = user_profile.get("preferred_subject")
        self.seen.append(
            {
                "user_id": user_id,
                "chat_type": chat_type,
                "current_class": class_num,
                "preferred_subject": subject,
                "message": user_message,
            }
        )
        if not class_num or not subject:
            return "need class and subject"
        url = await self.notes.get_folder_link(class_num, subject, "Notes")
        if url:
            return url
        return f"no notes folder for class {class_num} {subject}"


async def table_count(connection, table, where=None) -> int:
    query = select(func.count()).select_from(table)
    if where is not None:
        query = query.where(where)
    value = await connection.scalar(query)
    return int(value or 0)


async def snapshot(connection) -> dict:
    return {
        "students_real": await table_count(connection, students, outside_test_range(students.c.telegram_user_id)),
        "warnings_real": await table_count(connection, warnings, outside_test_range(warnings.c.telegram_user_id)),
        "events_real": await table_count(
            connection, interaction_events, outside_test_range(interaction_events.c.telegram_user_id)
        ),
        "students_test": await table_count(connection, students, in_test_range(students.c.telegram_user_id)),
        "warnings_test": await table_count(connection, warnings, in_test_range(warnings.c.telegram_user_id)),
        "events_test": await table_count(
            connection, interaction_events, in_test_range(interaction_events.c.telegram_user_id)
        ),
        "content_items": await table_count(connection, content_items),
        "folders": await table_count(connection, folders),
    }


async def check_catalog(database: Database, failures: list) -> dict:
    notes = NoteService(PostgresNoteRepository(database))
    async with database.engine.connect() as connection:
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
    paths = {row.path: row for row in folder_rows}
    class_12_ai = paths.get("Class 12/AI/Notes")
    if class_12_ai is None or class_12_ai.drive_folder_id != "129Kuy43zVF-eeDATsmGEi7xailM0FW7M":
        failures.append("class 12 AI notes folder is missing")
    for path in ("Class 10/AI/Notes/2026", "Class 10/AI/Notes/2027"):
        if path not in paths:
            failures.append(f"missing {path}")
    for path in REMOVED_PATHS:
        if path in paths:
            failures.append(f"{path} is still present")

    stored = [(row.path, row.url) for row in folder_rows]
    folders_checked = 0
    for row in folder_rows:
        parts = row.path.split("/")
        if len(parts) < 3 or not parts[0].startswith("Class "):
            continue
        class_num = int(parts[0].removeprefix("Class "))
        topic = parts[3] if len(parts) >= 4 else None
        expected = f"Class {class_num}/{parts[1]}/{parts[2]}"
        if topic:
            expected = f"{expected}/{topic}"
        url = choose_folder_url(stored, expected, topic)
        folders_checked += 1
        if url != row.url:
            failures.append(f"folder lookup missed {row.path}")
    live_notes = await notes.get_folder_link(12, "AI", "Notes")
    if class_12_ai is not None and live_notes != class_12_ai.url:
        failures.append("live Class 12 AI notes lookup missed")

    files_checked = 0
    for row in file_rows:
        if not row.level.startswith("Class "):
            failures.append(f"odd file level {row.title}")
            continue
        class_num = int(row.level.removeprefix("Class "))
        found = await notes.get_notes(class_num, row.subject, row.resource_type, row.topic or None)
        files_checked += 1
        if not any(note.title == row.title for note in found):
            failures.append(f"file lookup missed {row.title}")

    sample = await notes.get_folder_link(10, "AI", "Sample Question Papers")
    if not sample:
        failures.append("Class 10 AI sample papers did not match the SQP folder")
    class_11_it = await notes.get_notes(11, "IT", "Sample Question Papers")
    if class_11_it:
        failures.append("Class 11 IT sample papers were returned, and that folder is not in Drive")
    return {"folders_checked": folders_checked, "files_checked": files_checked}


async def seed_profiles(database: Database, failures: list) -> None:
    users = PostgresUserService(database)
    for offset in range(TEST_COUNT):
        user_id = user_id_for(offset)
        created = await users.get_user_profile(user_id, username=username_for(offset))
        if created.get("current_class") is not None or created.get("preferred_subject") is not None:
            failures.append(f"{user_id} was not created blank")
            return
        if offset >= 92:
            continue
        if offset == 0:
            await users.update_user_profile(
                user_id,
                {"current_class": 10, "preferred_subject": "AI", "class_updated_year": 2025},
            )
            promoted = await PostgresUserService(database).get_user_profile(user_id)
            if promoted.get("current_class") != 11 or promoted.get("class_updated_year") != 2026:
                failures.append(f"promotion stored {promoted}")
            continue
        if offset == 1:
            await users.update_user_profile(
                user_id,
                {"current_class": 12, "preferred_subject": "CS", "class_updated_year": 2025},
            )
            stayed = await PostgresUserService(database).get_user_profile(user_id)
            if stayed.get("current_class") != 12:
                failures.append(f"class 12 changed to {stayed}")
            continue
        if offset == 2:
            await users.update_user_profile(
                user_id,
                {"current_class": 11, "preferred_subject": "AI", "class_updated_year": 2026},
            )
            fresh = PostgresUserService(database)
            try:
                await fresh.update_user_profile(user_id, {"current_class": 9})
            except IntegrityError:
                pass
            else:
                failures.append("class 9 was stored")
            try:
                await fresh.update_user_profile(user_id, {"preferred_subject": "Math"})
            except IntegrityError:
                pass
            else:
                failures.append("subject Math was stored")
            continue
        await users.update_user_profile(
            user_id,
            {
                "current_class": CLASSES[offset % 3],
                "preferred_subject": SUBJECTS[offset % 4],
                "class_updated_year": 2026,
            },
        )


async def send_messages(database: Database, failures: list) -> int:
    notes = NoteService(PostgresNoteRepository(database))
    users = PostgresUserService(database)
    agent = NotesAgent(notes)
    runtime = ChatRuntime(agent=agent, user_service=users)
    logger_service = InteractionLoggingService(
        mode="postgres",
        postgres_repository=PostgresInteractionRepository(database.engine),
    )
    logged = 0
    for offset in range(TEST_COUNT):
        if offset % 25 == 0:
            print(f"messages {offset}", flush=True)
        user_id = user_id_for(offset)
        message = ChatMessage(
            platform=Platform.TELEGRAM,
            platform_user_id=str(user_id),
            platform_chat_id=str(user_id),
            chat_type=ChatType.PRIVATE,
            text="notes",
            username=username_for(offset),
        )
        response = await runtime.handle(message)
        if response.reply_mode != ReplyMode.REPLY or not response.text:
            failures.append(f"private notes for {username_for(offset)} did not reply")
            continue
        seen = agent.seen[-1]
        expected = expected_profile(offset)
        if (
            seen["current_class"] != expected["current_class"]
            or seen["preferred_subject"] != expected["preferred_subject"]
        ):
            failures.append(f"runtime profile for {username_for(offset)} was {seen}")
        event = InteractionEvent(
            telegram_update_id=user_id,
            telegram_user_id=user_id,
            user_message=message.text,
            bot_response=response.text,
            intent_output="agent",
            source_ref=f"test_seed:{user_id}",
        )
        report = await logger_service.log(event)
        if not report.success:
            failures.append(f"log write failed for {username_for(offset)}")
            continue
        logged += 1

    group_user = user_id_for(3)
    group_response = await runtime.handle(
        ChatMessage(
            platform=Platform.TELEGRAM,
            platform_user_id=str(group_user),
            platform_chat_id=str(TEST_CHAT_A),
            chat_type=ChatType.SUPERGROUP,
            text="@askai_bot notes",
            username=username_for(3),
            is_bot_mentioned=True,
            bot_username="askai_bot",
            group_title="Class 10 AI",
        )
    )
    if group_response.metadata.get("route") != "group_agent":
        failures.append(f"group notes route was {group_response.metadata.get('route')}")

    incomplete = await runtime.handle(
        ChatMessage(
            platform=Platform.TELEGRAM,
            platform_user_id=str(user_id_for(92)),
            platform_chat_id=str(TEST_CHAT_A),
            chat_type=ChatType.SUPERGROUP,
            text="@askai_bot notes",
            username=username_for(92),
            is_bot_mentioned=True,
            bot_username="askai_bot",
            group_title="Study group",
        )
    )
    if incomplete.metadata.get("route") != "group_insufficient_context":
        failures.append(f"incomplete group route was {incomplete.metadata.get('route')}")

    silent = await runtime.handle(
        ChatMessage(
            platform=Platform.TELEGRAM,
            platform_user_id=str(group_user),
            platform_chat_id=str(TEST_CHAT_A),
            chat_type=ChatType.SUPERGROUP,
            text="hello",
            username=username_for(3),
            is_bot_mentioned=False,
        )
    )
    if silent.reply_mode != ReplyMode.SILENT:
        failures.append("an unmentioned group message got a reply")
    return logged


async def record_warnings(database: Database, failures: list) -> None:
    strikes = PostgresWarningService(database)
    user_id = user_id_for(0)
    username = username_for(0)
    first = await strikes.add_warning(user_id, TEST_CHAT_A, username=username)
    if first.warning_count != 1 or first.should_ban:
        failures.append(f"first warning was {first.warning_count}")
    second = await strikes.add_warning(user_id, TEST_CHAT_A, username=username)
    if second.warning_count != 2 or not second.should_ban:
        failures.append(f"second warning was {second.warning_count}")
    other = await strikes.add_warning(user_id, TEST_CHAT_B, username=username)
    if other.warning_count != 1 or other.should_ban:
        failures.append(f"other chat warning was {other.warning_count}")
    fresh = PostgresWarningService(database)
    banned_here = await fresh.is_banned(user_id, TEST_CHAT_A)
    banned_there = await fresh.is_banned(user_id, TEST_CHAT_B)
    if not banned_here or banned_there:
        failures.append(f"ban scope first={banned_here} second={banned_there}")


async def verify_rows(database: Database, failures: list) -> None:
    async with database.engine.connect() as connection:
        rows = (
            await connection.execute(
                select(
                    students.c.telegram_user_id,
                    students.c.username,
                    students.c.current_class,
                    students.c.preferred_subject,
                    students.c.class_updated_year,
                ).where(in_test_range(students.c.telegram_user_id))
            )
        ).all()
        warning_rows = (
            await connection.execute(
                select(
                    warnings.c.telegram_user_id,
                    warnings.c.telegram_chat_id,
                    warnings.c.warning_count,
                    warnings.c.banned,
                ).where(in_test_range(warnings.c.telegram_user_id))
            )
        ).all()
        event_count = await table_count(
            connection, interaction_events, in_test_range(interaction_events.c.telegram_user_id)
        )
    by_id = {int(row.telegram_user_id): row for row in rows}
    if len(by_id) != TEST_COUNT:
        failures.append(f"expected 100 test students, found {len(by_id)}")
        return
    for offset in range(TEST_COUNT):
        row = by_id.get(user_id_for(offset))
        expected = expected_profile(offset)
        if row is None or row.username != username_for(offset):
            failures.append(f"missing {username_for(offset)}")
            continue
        if (
            row.current_class != expected["current_class"]
            or row.preferred_subject != expected["preferred_subject"]
            or int(row.class_updated_year) != expected["class_updated_year"]
        ):
            failures.append(
                f"{row.username} is class {row.current_class} {row.preferred_subject} "
                f"year {row.class_updated_year}"
            )
    warning_map = {(int(row.telegram_user_id), int(row.telegram_chat_id)): row for row in warning_rows}
    banned = warning_map.get((user_id_for(0), TEST_CHAT_A))
    open_warning = warning_map.get((user_id_for(0), TEST_CHAT_B))
    if banned is None or banned.warning_count != 2 or not banned.banned:
        failures.append("banned test warning is missing")
    if open_warning is None or open_warning.warning_count != 1 or open_warning.banned:
        failures.append("second-chat test warning is missing")
    if len(warning_map) != 2:
        failures.append(f"expected 2 test warnings, found {len(warning_map)}")
    if event_count != TEST_COUNT:
        failures.append(f"expected 100 test log rows, found {event_count}")


async def run() -> dict:
    database = Database(supabase_url())
    failures: list[str] = []
    try:
        async with database.engine.connect() as connection:
            await connection.execute(select(1))
            before = await snapshot(connection)
        already = before["students_test"]
        logged = 0
        if already == 0:
            await seed_profiles(database, failures)
        elif already != TEST_COUNT:
            failures.append(f"{already} test students exist, expected 0 or 100")
        if before["events_test"] == 0 and already in (0, TEST_COUNT) and not any(
            item.startswith(f"{already} test students") for item in failures
        ):
            logged = await send_messages(database, failures)
        if before["warnings_test"] == 0 and already in (0, TEST_COUNT):
            await record_warnings(database, failures)
        catalog = await check_catalog(database, failures)
        await verify_rows(database, failures)
        async with database.engine.connect() as connection:
            after = await snapshot(connection)
        for key in ("students_real", "warnings_real", "events_real", "content_items", "folders"):
            if before[key] != after[key]:
                failures.append(f"{key} changed from {before[key]} to {after[key]}")
        return {
            "status": "ok" if not failures else "failed",
            "mode": "seeded" if already == 0 else "completed",
            "failed": len(failures),
            "failures": failures[:20],
            "logged": logged,
            "before": before,
            "after": after,
            **catalog,
        }
    finally:
        await database.close()


def main() -> int:
    try:
        summary = asyncio.run(run())
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "error": type(exc).__name__}, sort_keys=True))
        return 2
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
