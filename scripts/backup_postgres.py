#!/usr/bin/env python3
"""Write a custom-format dump of the bot database.

Reads DATABASE_URL from the environment. The URL is not printed.
The dump goes under artifacts/ and is gitignored because it contains
student ids and messages.

--restore-drill loads that dump into a temporary database, checks the
table counts, and drops the temporary database.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.engine import make_url

TABLES = (
    "alembic_version",
    "students",
    "content_items",
    "folders",
    "warnings",
    "interaction_events",
)
DRILL_DATABASE = "ask_ai_restore_drill"


def redact(text: str) -> str:
    return re.sub(r"postgres(?:ql)?(?:\+[^:/]+)?://\S+", "postgresql://redacted", text)


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"{name} is not installed")
    return path


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    parsed = make_url(url)
    if parsed.drivername.startswith("postgres") is False and parsed.drivername != "postgresql+asyncpg":
        raise RuntimeError("DATABASE_URL must be a PostgreSQL URL")
    if parsed.drivername == "postgresql+asyncpg":
        parsed = parsed.set(drivername="postgresql")
    return parsed.render_as_string(hide_password=False)


def with_database(url: str, database: str) -> str:
    return make_url(url).set(database=database).render_as_string(hide_password=False)


def run(command: list[str], *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, input=input_bytes, text=input_bytes is None, capture_output=True)
    if completed.returncode != 0:
        stderr = completed.stderr if isinstance(completed.stderr, str) else completed.stderr.decode()
        stdout = completed.stdout if isinstance(completed.stdout, str) else completed.stdout.decode()
        detail = redact((stderr or stdout or "").strip())
        raise RuntimeError(detail or f"command failed with exit {completed.returncode}")
    return completed


def local_container(url: str) -> bool:
    parsed = make_url(url)
    return parsed.host in {"127.0.0.1", "localhost"} and parsed.port == 5433


def dump_database(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    parsed = make_url(url)
    if local_container(url):
        completed = subprocess.run(
            [
                "docker",
                "exec",
                "-e",
                f"PGPASSWORD={parsed.password or ''}",
                "ask-ai-postgres",
                "pg_dump",
                "-U",
                parsed.username or "bot",
                "-d",
                parsed.database or "ask_ai",
                "--format=custom",
                "--no-owner",
                "--no-acl",
            ],
            capture_output=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(redact(completed.stderr.decode().strip()) or "pg_dump failed")
        destination.write_bytes(completed.stdout)
        return
    run(
        [
            require_tool("pg_dump"),
            "--format=custom",
            "--no-owner",
            "--no-acl",
            f"--file={destination}",
            url,
        ]
    )


def assert_archive(path: Path) -> None:
    listing = run([require_tool("pg_restore"), "--list", str(path)]).stdout
    missing = [name for name in TABLES if f"TABLE DATA public {name} " not in listing]
    if missing:
        raise RuntimeError("dump is missing tables: " + ", ".join(missing))


def psql_command(url: str, database: str, sql: str, *, tuples_only: bool = False) -> list[str]:
    parsed = make_url(url)
    flags = ["-tA", "-c", sql] if tuples_only else ["-c", sql]
    if local_container(url):
        return [
            "docker",
            "exec",
            "-e",
            f"PGPASSWORD={parsed.password or ''}",
            "ask-ai-postgres",
            "psql",
            "-U",
            parsed.username or "bot",
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
            *flags,
        ]
    return [
        require_tool("psql"),
        with_database(url, database),
        "-v",
        "ON_ERROR_STOP=1",
        *flags,
    ]


def restore_drill(url: str, dump_path: Path) -> dict[str, str]:
    admin_name = "postgres"
    run(psql_command(url, admin_name, f"DROP DATABASE IF EXISTS {DRILL_DATABASE}"))
    run(psql_command(url, admin_name, f"CREATE DATABASE {DRILL_DATABASE}"))
    try:
        if local_container(url):
            parsed = make_url(url)
            run(
                [
                    "docker",
                    "exec",
                    "-i",
                    "-e",
                    f"PGPASSWORD={parsed.password or ''}",
                    "ask-ai-postgres",
                    "pg_restore",
                    "-U",
                    parsed.username or "bot",
                    "-d",
                    DRILL_DATABASE,
                    "--no-owner",
                    "--no-acl",
                ],
                input_bytes=dump_path.read_bytes(),
            )
        else:
            run(
                [
                    require_tool("pg_restore"),
                    "--no-owner",
                    "--no-acl",
                    f"--dbname={with_database(url, DRILL_DATABASE)}",
                    str(dump_path),
                ]
            )
        counts: dict[str, str] = {}
        for table in TABLES:
            if table == "alembic_version":
                sql = "SELECT version_num FROM alembic_version"
            else:
                sql = f"SELECT count(*) FROM {table}"
            value = run(psql_command(url, DRILL_DATABASE, sql, tuples_only=True)).stdout.strip()
            counts[table] = value
        return counts
    finally:
        run(psql_command(url, "postgres", f"DROP DATABASE IF EXISTS {DRILL_DATABASE}"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dump the bot database. The URL is not printed.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Dump path. Defaults to artifacts/ask-ai-<utc timestamp>.dump",
    )
    parser.add_argument(
        "--restore-drill",
        action="store_true",
        help=f"Restore into {DRILL_DATABASE}, check counts, then drop that database",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = args.output or Path("artifacts") / f"ask-ai-{stamp}.dump"
    try:
        url = database_url()
        dump_database(url, destination)
        assert_archive(destination)
        print(f"dump={destination}")
        print(f"bytes={destination.stat().st_size}")
        if args.restore_drill:
            counts = restore_drill(url, destination)
            for name in TABLES:
                print(f"{name}={counts[name]}")
    except (OSError, RuntimeError, ValueError) as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
