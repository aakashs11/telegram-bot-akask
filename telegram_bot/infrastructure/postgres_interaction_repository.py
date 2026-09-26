"""PostgreSQL interaction repository implemented with SQLAlchemy async."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, insert
from sqlalchemy.ext.asyncio import AsyncEngine

from telegram_bot.domain.interactions import InteractionEvent, InteractionRepository


metadata = MetaData()

interaction_events = Table(
    "interaction_events",
    metadata,
    Column("event_id", UUID(as_uuid=True), nullable=False),
    Column("telegram_update_id", BigInteger, nullable=True),
    Column("telegram_user_id", BigInteger, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("user_message", Text, nullable=False),
    Column("bot_response", Text, nullable=False),
    Column("screener_output", Text, nullable=False),
    Column("intent_output", Text, nullable=False),
    Column("entities_output", Text, nullable=False),
    Column("source_ref", Text, nullable=True),
    Column("source_timestamp_raw", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("event_id", name="pk_interaction_events"),
    UniqueConstraint(
        "telegram_update_id",
        name="uq_interaction_events_telegram_update_id",
    ),
    UniqueConstraint("source_ref", name="uq_interaction_events_source_ref"),
    Index("ix_interaction_events_occurred_at", "occurred_at"),
    Index("ix_interaction_events_telegram_user_id", "telegram_user_id"),
)


class PostgresInteractionRepository(InteractionRepository):
    """Persist immutable events with idempotent conflict handling."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def add(self, event: InteractionEvent) -> bool:
        statement = (
            insert(interaction_events)
            .values(
                event_id=event.event_id,
                telegram_update_id=event.telegram_update_id,
                telegram_user_id=event.telegram_user_id,
                occurred_at=event.occurred_at,
                user_message=event.user_message,
                bot_response=event.bot_response,
                screener_output=event.screener_output,
                intent_output=event.intent_output,
                entities_output=event.entities_output,
                source_ref=event.source_ref,
                source_timestamp_raw=event.source_timestamp_raw,
                created_at=event.created_at,
            )
            .on_conflict_do_nothing()
        )

        async with self._engine.begin() as connection:
            result = await connection.execute(statement)
        return result.rowcount == 1
