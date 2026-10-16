"""Validation rules for the UserProfiles copy."""

from scripts.copy_student_profiles import (
    validate_profile_headers,
    validate_profile_row,
)
from scripts.interaction_log_migration import SourceRow, timezone_from_name


def test_blank_class_and_subject_become_null() -> None:
    profile = validate_profile_row(
        SourceRow(
            2,
            ("4242", "riya", "", "", "2026-10-03T12:00:00", "2026-10-03T12:00:00", ""),
        ),
        source_timezone=timezone_from_name("Asia/Kolkata"),
    )

    assert profile.telegram_user_id == 4242
    assert profile.current_class is None
    assert profile.preferred_subject is None
    assert profile.class_updated_year == 0
    assert profile.created_at.isoformat() == "2026-10-03T06:30:00+00:00"


def test_invalid_class_and_subject_are_rejected() -> None:
    zone = timezone_from_name("UTC")
    row = ("4242", "riya", "9", "AI", "2026-10-03T12:00:00Z", "2026-10-03T12:00:00Z", "2026")
    try:
        validate_profile_row(SourceRow(2, row), source_timezone=zone)
    except ValueError as exc:
        assert "current_class" in str(exc)
    else:
        raise AssertionError("class 9 should be rejected")

    try:
        validate_profile_row(
            SourceRow(3, ("4242", "riya", "10", "Math", "2026-10-03T12:00:00Z", "2026-10-03T12:00:00Z", "2026")),
            source_timezone=zone,
        )
    except ValueError as exc:
        assert "preferred_subject" in str(exc)
    else:
        raise AssertionError("subject Math should be rejected")


def test_headers_must_match_the_userprofiles_sheet() -> None:
    validate_profile_headers(
        (
            "user_id",
            "username",
            "current_class",
            "preferred_subject",
            "created_at",
            "last_updated",
            "class_updated_year",
        )
    )
    try:
        validate_profile_headers(("Timestamp", "User ID"))
    except ValueError as exc:
        assert "headers" in str(exc)
    else:
        raise AssertionError("wrong headers should be rejected")
