"""Shared pytest configuration and PostgreSQL integration-test provisioning."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest


# Application imports validate these settings at module import time. Tests use
# fakes and never contact Telegram or OpenAI.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: requires a disposable PostgreSQL database",
    )


def _docker_test_database() -> Iterator[str]:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip(
            "PostgreSQL integration skipped: TEST_DATABASE_URL is unset "
            "and Docker is not installed"
        )

    daemon = subprocess.run(
        [docker, "info"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if daemon.returncode != 0:
        pytest.skip(
            "PostgreSQL integration skipped: TEST_DATABASE_URL is unset "
            "and the Docker daemon is unavailable"
        )

    started = subprocess.run(
        [
            docker,
            "run",
            "--rm",
            "--detach",
            "--publish",
            "127.0.0.1::5432",
            "--env",
            "POSTGRES_USER=test_user",
            "--env",
            "POSTGRES_PASSWORD=test_password",
            "--env",
            "POSTGRES_DB=interaction_test",
            "postgres:16-alpine",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if started.returncode != 0:
        pytest.skip(
            "PostgreSQL integration skipped: Docker could not start the "
            f"postgres:16-alpine test container ({started.stderr.strip()})"
        )

    container_id = started.stdout.strip()
    try:
        port_result = subprocess.run(
            [docker, "port", container_id, "5432/tcp"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        port = int(port_result.stdout.strip().rsplit(":", 1)[1])
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                time.sleep(0.25)
        else:
            pytest.fail("Docker PostgreSQL did not accept connections in 30 seconds")

        yield (
            "postgresql+asyncpg://test_user:test_password"
            f"@127.0.0.1:{port}/interaction_test"
        )
    finally:
        subprocess.run(
            [docker, "rm", "--force", container_id],
            capture_output=True,
            text=True,
            timeout=30,
        )


@pytest.fixture(scope="session")
def postgres_test_url() -> Iterator[str]:
    """Return an explicitly configured or ephemeral disposable database URL."""
    configured_url = os.getenv("TEST_DATABASE_URL")
    if configured_url:
        yield configured_url
        return
    yield from _docker_test_database()


@pytest.fixture(scope="session")
def migrated_postgres_url(postgres_test_url: str) -> str:
    """Apply the complete Alembic history to the disposable test database."""
    environment = os.environ.copy()
    environment["DATABASE_URL"] = postgres_test_url

    for command in (("downgrade", "base"), ("upgrade", "head")):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *command],
            cwd=REPOSITORY_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            pytest.fail(
                f"Alembic {' '.join(command)} failed:\n"
                f"{result.stdout}\n{result.stderr}"
            )

    return postgres_test_url
