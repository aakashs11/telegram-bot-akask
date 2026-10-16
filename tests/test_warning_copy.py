"""Validation rules for the Warnings sheet copy."""

from scripts.copy_warnings import prefer_warning, validate_warning_headers, validate_warning_row
from scripts.interaction_log_migration import SourceRow, timezone_from_name
from telegram_bot.services.postgres_warning_service import warning_crosses_ban


def test_warning_row_keeps_both_ids() -> None:
    warning = validate_warning_row(
        SourceRow(
            2,
            ("4242", "-10099", "riya", "1", "content_violation", "2026-10-03T12:00:00", "FALSE"),
        ),
        source_timezone=timezone_from_name("UTC"),
    )

    assert warning.telegram_user_id == 4242
    assert warning.telegram_chat_id == -10099
    assert warning.warning_count == 1
    assert warning.banned is False
    assert warning.last_warning.isoformat() == "2026-10-03T12:00:00+00:00"


def test_bad_banned_value_is_rejected() -> None:
    try:
        validate_warning_row(
            SourceRow(
                3,
                ("4242", "99", "riya", "1", "spam", "2026-10-03T12:00:00Z", "yes"),
            ),
            source_timezone=timezone_from_name("UTC"),
        )
    except ValueError as exc:
        assert "banned" in str(exc)
    else:
        raise AssertionError("banned yes should be rejected")


def test_headers_must_match_the_warnings_sheet() -> None:
    validate_warning_headers(
        (
            "user_id",
            "chat_id",
            "username",
            "warning_count",
            "last_reason",
            "last_warning",
            "banned",
        )
    )
    try:
        validate_warning_headers(("user_id", "chat_id"))
    except ValueError as exc:
        assert "headers" in str(exc)
    else:
        raise AssertionError("wrong headers should be rejected")


def test_duplicate_chat_keeps_the_higher_count() -> None:
    zone = timezone_from_name("UTC")
    first = validate_warning_row(
        SourceRow(159, ("7", "-100", "m", "1", "content_violation", "2026-09-24T11:20:38", "FALSE")),
        source_timezone=zone,
    )
    banned = validate_warning_row(
        SourceRow(171, ("7", "-100", "m", "13", "content_violation", "2026-09-24T11:22:17", "TRUE")),
        source_timezone=zone,
    )
    later_reset = validate_warning_row(
        SourceRow(178, ("7", "-100", "m", "1", "content_violation", "2026-10-09T12:29:11", "FALSE")),
        source_timezone=zone,
    )

    assert prefer_warning(first, banned) is banned
    assert prefer_warning(banned, later_reset) is banned


def test_second_warning_bans() -> None:
    assert warning_crosses_ban(0) == (1, False)
    assert warning_crosses_ban(1) == (2, True)
