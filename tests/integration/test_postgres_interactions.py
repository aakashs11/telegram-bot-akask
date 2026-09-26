"""PostgreSQL repository and Alembic integration coverage."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from telegram_bot.domain.interactions import InteractionEvent
from telegram_bot.infrastructure.database import Database, async_database_url
from telegram_bot.infrastructure.postgres_interaction_repository import (
    PostgresInteractionRepository,
    interaction_events,
)

pytestmark = pytest.mark.integration


async def clean_engine(database_url: str) -> AsyncEngine:
    engine = create_async_engine(async_database_url(database_url))
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE TABLE interaction_events"))
    return engine


@pytest.mark.asyncio
async def test_alembic_head_creates_expected_schema(
    migrated_postgres_url: str,
) -> None:
    engine = create_async_engine(async_database_url(migrated_postgres_url))
    try:
        async with engine.connect() as connection:
            schema = await connection.run_sync(
                lambda sync_connection: {
                    "columns": {
                        column["name"]
                        for column in inspect(sync_connection).get_columns(
                            "interaction_events"
                        )
                    },
                    "primary_key": set(
                        inspect(sync_connection)
                        .get_pk_constraint("interaction_events")[
                            "constrained_columns"
                        ]
                    ),
                    "unique_constraints": {
                        constraint["name"]
                        for constraint in inspect(
                            sync_connection
                        ).get_unique_constraints("interaction_events")
                    },
                    "indexes": {
                        index["name"]
                        for index in inspect(sync_connection).get_indexes(
                            "interaction_events"
                        )
                    },
                }
            )
            revision = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )

        assert schema["columns"] == {
            "event_id",
            "telegram_update_id",
            "telegram_user_id",
            "occurred_at",
            "user_message",
            "bot_response",
            "screener_output",
            "intent_output",
            "entities_output",
            "source_ref",
            "source_timestamp_raw",
            "created_at",
        }
        assert schema["primary_key"] == {"event_id"}
        assert {
            "uq_interaction_events_telegram_update_id",
            "uq_interaction_events_source_ref",
        } <= schema["unique_constraints"]
        assert {
            "ix_interaction_events_occurred_at",
            "ix_interaction_events_telegram_user_id",
        } <= schema["indexes"]
        assert revision == "20260922_0001"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_normal_insert_persists_event(
    migrated_postgres_url: str,
) -> None:
    engine = await clean_engine(migrated_postgres_url)
    repository = PostgresInteractionRepository(engine)
    event = InteractionEvent(
        telegram_user_id=42,
        telegram_update_id=1001,
        source_ref="live:1001",
        user_message="What is iteration?",
        bot_response="Iteration repeats a sequence.",
        screener_output="safe",
        intent_output="explanation",
        entities_output="loops",
    )
    try:
        assert await repository.add(event) is True
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    select(interaction_events).where(
                        interaction_events.c.event_id == event.event_id
                    )
                )
            ).mappings().one()

        assert row["telegram_user_id"] == event.telegram_user_id
        assert row["telegram_update_id"] == event.telegram_update_id
        assert row["user_message"] == event.user_message
        assert row["bot_response"] == event.bot_response
        assert row["source_ref"] == event.source_ref
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_event_id_is_idempotently_skipped(
    migrated_postgres_url: str,
) -> None:
    engine = await clean_engine(migrated_postgres_url)
    repository = PostgresInteractionRepository(engine)
    event = InteractionEvent(
        telegram_user_id=42,
        user_message="First",
        bot_response="First response",
    )
    try:
        assert await repository.add(event) is True
        assert await repository.add(event) is False
        async with engine.connect() as connection:
            count = await connection.scalar(
                text("SELECT count(*) FROM interaction_events")
            )
        assert count == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_telegram_update_id_is_idempotently_skipped(
    migrated_postgres_url: str,
) -> None:
    engine = await clean_engine(migrated_postgres_url)
    repository = PostgresInteractionRepository(engine)
    first = InteractionEvent(
        telegram_user_id=42,
        telegram_update_id=555,
        user_message="First delivery",
        bot_response="Response",
    )
    retry = InteractionEvent(
        event_id=uuid4(),
        telegram_user_id=42,
        telegram_update_id=555,
        user_message="Telegram retry",
        bot_response="Response",
    )
    try:
        assert await repository.add(first) is True
        assert await repository.add(retry) is False
        async with engine.connect() as connection:
            event_ids = (
                await connection.scalars(
                    select(interaction_events.c.event_id)
                )
            ).all()
        assert event_ids == [first.event_id]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_unicode_and_long_text_round_trip(
    migrated_postgres_url: str,
) -> None:
    engine = await clean_engine(migrated_postgres_url)
    repository = PostgresInteractionRepository(engine)
    long_message = "नमस्ते विद्यार्थी! 🧠📚 — " + ("अ" * 50_000)
    long_response = "Python 🐍: " + ("iteration " * 10_000)
    event = InteractionEvent(
        telegram_user_id=99,
        user_message=long_message,
        bot_response=long_response,
    )
    try:
        assert await repository.add(event) is True
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    select(
                        interaction_events.c.user_message,
                        interaction_events.c.bot_response,
                    )
                )
            ).one()
        assert row.user_message == long_message
        assert row.bot_response == long_response
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_optional_values_use_safe_defaults_and_null_identifiers(
    migrated_postgres_url: str,
) -> None:
    engine = await clean_engine(migrated_postgres_url)
    repository = PostgresInteractionRepository(engine)
    event = InteractionEvent(
        telegram_user_id=7,
        user_message="hello",
        bot_response="hi",
    )
    try:
        assert await repository.add(event) is True
        async with engine.connect() as connection:
            row = (
                await connection.execute(select(interaction_events))
            ).mappings().one()
        assert row["telegram_update_id"] is None
        assert row["source_ref"] is None
        assert row["screener_output"] == ""
        assert row["intent_output"] == ""
        assert row["entities_output"] == ""
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_connection_failure_is_reported_by_healthcheck_and_repository() -> None:
    database = Database(
        "postgresql://test:test@127.0.0.1:1/unreachable",
        pool_size=1,
        max_overflow=0,
        pool_timeout_seconds=0.1,
    )
    repository = PostgresInteractionRepository(database.engine)
    event = InteractionEvent(
        telegram_user_id=1,
        user_message="message",
        bot_response="response",
    )
    try:
        assert await database.healthcheck() is False
        with pytest.raises(Exception):
            await repository.add(event)
    finally:
        await database.close()
