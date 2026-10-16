"""Unit coverage for provider-neutral PostgreSQL URL normalization."""

from sqlalchemy.engine import make_url

from telegram_bot.infrastructure.database import async_database_url


def test_async_database_url_normalizes_libpq_sslmode() -> None:
    normalized = make_url(
        async_database_url(
            "postgresql://bot:secret@db.example/ask_ai?sslmode=require"
        )
    )

    assert normalized.drivername == "postgresql+asyncpg"
    assert normalized.query == {"ssl": "require"}


def test_async_database_url_preserves_native_asyncpg_ssl() -> None:
    normalized = make_url(
        async_database_url(
            "postgresql+asyncpg://bot:secret@db.example/ask_ai?ssl=verify-full"
        )
    )

    assert normalized.query == {"ssl": "verify-full"}
