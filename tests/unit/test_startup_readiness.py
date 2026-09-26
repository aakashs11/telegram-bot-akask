"""Startup readiness behavior for optional interaction-log PostgreSQL."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

import main


class UnavailableDatabase:
    instances: list["UnavailableDatabase"] = []

    def __init__(self, database_url: str, **kwargs) -> None:
        self.database_url = database_url
        self.engine = object()
        self.closed = False
        self.instances.append(self)

    async def healthcheck(self) -> bool:
        return False

    async def close(self) -> None:
        self.closed = True


class FakePostgresRepository:
    def __init__(self, engine: object) -> None:
        self.engine = engine

    async def add(self, event) -> bool:
        return True


@pytest.mark.asyncio
async def test_dual_mode_alerts_but_starts_when_database_is_unready(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_url = "postgresql://student:do-not-log-me@db.invalid/ask_ai"
    fake_application = SimpleNamespace(bot_data={})
    fake_app = SimpleNamespace(state=SimpleNamespace())
    UnavailableDatabase.instances.clear()

    monkeypatch.setattr(main, "application", fake_application)
    monkeypatch.setattr(main, "CLOUD_RUN_URL", None)
    monkeypatch.setattr(main, "INTERACTION_LOG_MODE", "dual")
    monkeypatch.setattr(main, "DATABASE_URL", secret_url)
    monkeypatch.setattr(main, "Database", UnavailableDatabase)
    monkeypatch.setattr(
        main,
        "PostgresInteractionRepository",
        FakePostgresRepository,
    )
    caplog.set_level(logging.INFO)

    reached_application_startup = False
    async with main.lifespan(fake_app):
        reached_application_startup = True
        service = fake_application.bot_data["interaction_logging_service"]
        assert service.mode.value == "dual"
        assert fake_app.state.interaction_database is UnavailableDatabase.instances[0]

    assert reached_application_startup is True
    assert UnavailableDatabase.instances[0].closed is True
    assert "Interaction database health check failed" in caplog.text
    assert "database_ready=False" in caplog.text
    assert secret_url not in caplog.text
    assert "do-not-log-me" not in caplog.text
