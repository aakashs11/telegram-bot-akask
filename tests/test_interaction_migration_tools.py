from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
from uuid import uuid4

import pytest

from scripts.backfill_sheet_interactions import run
from scripts.interaction_log_migration import (
    SourceRow,
    deterministic_source_ref,
    field_hashes,
    parse_source_timestamp,
    rows_from_sheet_values,
    timezone_from_name,
    validate_headers,
    validate_row,
)


def test_legacy_timestamp_uses_explicit_timezone_and_preserves_raw() -> None:
    zone = timezone_from_name("Asia/Kolkata")
    raw = "2026-09-22 14:30:00"
    row = validate_row(
        SourceRow(42, (raw, "123", "question", "answer", "", "", "")),
        source_id="sheet-abc",
        source_timezone=zone,
        has_event_id=False,
    )

    assert row.event.occurred_at.isoformat() == "2026-09-22T09:00:00+00:00"
    assert row.event.source_timestamp_raw == raw
    assert row.event.source_ref == "sheet:sheet-abc:row:42"


def test_backfill_identity_is_deterministic_across_reruns() -> None:
    zone = timezone_from_name("UTC")
    source = SourceRow(
        2,
        ("2026-09-22T12:00:00Z", "99", "q", "a", "s", "i", "e"),
    )
    first = validate_row(
        source,
        source_id="source-1",
        source_timezone=zone,
        has_event_id=False,
    )
    second = validate_row(
        source,
        source_id="source-1",
        source_timezone=zone,
        has_event_id=False,
    )

    assert first.event.source_ref == second.event.source_ref
    assert first.event.event_id == second.event.event_id
    assert deterministic_source_ref("source-1", 2) == "sheet:source-1:row:2"


def test_seven_column_contract_rejects_bad_headers_and_rows() -> None:
    assert not validate_headers(
        (
            "Timestamp",
            "User ID",
            "User Message",
            "Bot Response",
            "Screener",
            "Intent",
            "Entities",
        )
    )
    with pytest.raises(ValueError, match="headers"):
        validate_headers(("time", "user"))
    with pytest.raises(ValueError, match="expected 7 columns"):
        validate_row(
            SourceRow(2, ("2026-09-22 10:00:00", "1")),
            source_id="source-1",
            source_timezone=timezone_from_name("UTC"),
            has_event_id=False,
        )


def test_field_hashes_normalize_timestamp_but_detect_payload_changes() -> None:
    zone = timezone_from_name("Asia/Kolkata")
    legacy = ("2026-09-22 14:30:00", "00123", "q", "a", "", "", "")
    utc = ("2026-09-22T09:00:00+00:00", "123", "q", "a", "", "", "")
    changed = ("2026-09-22T09:00:00+00:00", "123", "q", "different", "", "", "")

    assert field_hashes(legacy, source_timezone=zone) == field_hashes(
        utc,
        source_timezone=zone,
    )
    assert field_hashes(legacy, source_timezone=zone) != field_hashes(
        changed,
        source_timezone=zone,
    )


def test_dry_run_has_exact_accounting_and_rejected_report(tmp_path: Path) -> None:
    export = tmp_path / "logs.csv"
    rejects = tmp_path / "rejects.csv"
    with export.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            (
                "Timestamp",
                "User ID",
                "User Message",
                "Bot Response",
                "Screener",
                "Intent",
                "Entities",
            )
        )
        writer.writerow(("2026-09-22 14:30:00", "123", "q", "a", "", "", ""))
        writer.writerow(("bad timestamp", "456", "q2", "a2", "", "", ""))

    args = argparse.Namespace(
        csv=export,
        sheet_id=None,
        worksheet="Logs",
        credentials_file=None,
        source_id="sheet-abc",
        source_timezone="Asia/Kolkata",
        start_row=2,
        end_row=3,
        batch_size=1,
        rejects_file=rejects,
        database_url=None,
        apply=False,
    )
    summary = asyncio.run(run(args))

    assert summary["mode"] == "dry-run"
    assert summary["scanned"] == 2
    assert summary["would_import"] == 1
    assert summary["rejected"] == 1
    assert summary["scanned"] == summary["valid"] + summary["rejected"]
    assert "bad timestamp" in rejects.read_text(encoding="utf-8")


def test_aware_timestamp_does_not_get_reinterpreted() -> None:
    parsed = parse_source_timestamp(
        "2026-09-22T14:30:00+02:00",
        timezone_from_name("Asia/Kolkata"),
    )
    assert parsed.isoformat() == "2026-09-22T12:30:00+00:00"


def test_dual_write_event_id_is_preserved() -> None:
    event_id = uuid4()
    row = validate_row(
        SourceRow(
            8,
            (
                "2026-09-22T12:00:00+00:00",
                "123",
                "q",
                "a",
                "",
                "",
                "",
                str(event_id),
            ),
        ),
        source_id="sheet-abc",
        source_timezone=timezone_from_name("UTC"),
        has_event_id=True,
    )
    assert row.event_id_from_sheet == event_id
    assert row.event.event_id == event_id


def test_sheet_reader_pads_trailing_empty_cells() -> None:
    headers = (
        "Timestamp",
        "User ID",
        "User Message",
        "Bot Response",
        "Screener",
        "Intent",
        "Entities",
    )
    _, rows = rows_from_sheet_values(
        (headers, ("2026-09-22 10:00:00", "1", "q", "a"))
    )
    assert next(rows).values == (
        "2026-09-22 10:00:00",
        "1",
        "q",
        "a",
        "",
        "",
        "",
    )
