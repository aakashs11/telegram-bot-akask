"""Async SQLAlchemy database lifecycle for PostgreSQL."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def async_database_url(database_url: str) -> str:
    """Normalize PostgreSQL URLs for SQLAlchemy's asyncpg driver."""
    if not database_url or not database_url.strip():
        raise ValueError("DATABASE_URL must not be empty")

    url = make_url(database_url.strip())
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+asyncpg")
    elif url.drivername != "postgresql+asyncpg":
        raise ValueError("DATABASE_URL must use PostgreSQL")

    # Providers commonly publish libpq URLs with ``sslmode=require``.
    # asyncpg names the same connect argument ``ssl`` and otherwise receives
    # an unsupported ``sslmode`` keyword from SQLAlchemy.
    query = dict(url.query)
    sslmode = query.pop("sslmode", None)
    if sslmode is not None and "ssl" not in query:
        query["ssl"] = sslmode
    url = url.set(query=query)
    return url.render_as_string(hide_password=False)


class Database:
    """Own one async engine and session factory for the process."""

    def __init__(
        self,
        database_url: str,
        *,
        pool_size: int = 3,
        max_overflow: int = 2,
        pool_timeout_seconds: float = 10.0,
    ) -> None:
        self.engine: AsyncEngine = create_async_engine(
            async_database_url(database_url),
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout_seconds,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def healthcheck(self) -> bool:
        """Verify that a connection can execute a minimal query."""
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Release all pooled connections."""
        await self.engine.dispose()
