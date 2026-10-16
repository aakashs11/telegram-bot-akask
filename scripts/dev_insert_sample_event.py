"""Insert one practice interaction so you can see a real row. Local only."""

import asyncio
import os
from uuid import UUID

from telegram_bot.domain.interactions import InteractionEvent
from telegram_bot.infrastructure.database import Database
from telegram_bot.infrastructure.postgres_interaction_repository import (
    PostgresInteractionRepository,
)


async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    database = Database(database_url)
    repository = PostgresInteractionRepository(database.engine)

    event = InteractionEvent(
        telegram_update_id=1001,
        telegram_user_id=4242,
        user_message="notes for class 10 AI",
        bot_response="Here are the notes.",
        screener_output="allow",
        intent_output="get_notes",
        entities_output="class=10 subject=AI",
    )
    print("event_id", event.event_id)

    inserted = await repository.add(event)
    print("inserted", inserted)

    inserted_again = await repository.add(event)
    print("inserted_again", inserted_again)

    await database.close()


if __name__ == "__main__":
    asyncio.run(main())
