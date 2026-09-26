"""Domain contract for immutable interaction log events."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class InteractionEvent:
    """One user/bot interaction, generated once and shared by every sink."""

    telegram_user_id: int
    user_message: str
    bot_response: str
    screener_output: str = ""
    intent_output: str = ""
    entities_output: str = ""
    telegram_update_id: Optional[int] = None
    source_ref: Optional[str] = None
    source_timestamp_raw: Optional[str] = None
    occurred_at: datetime = field(default_factory=utc_now)
    event_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        for name in ("occurred_at", "created_at"):
            value = getattr(self, name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")


class InteractionRepository(ABC):
    """Provider-neutral asynchronous persistence boundary."""

    @abstractmethod
    async def add(self, event: InteractionEvent) -> bool:
        """Persist an event, returning False when an idempotent retry is skipped."""
        raise NotImplementedError
