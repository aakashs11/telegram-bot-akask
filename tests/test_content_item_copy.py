"""Validation rules for the Index sheet copy."""

from scripts.copy_content_items import validate_index_headers, validate_index_row
from scripts.interaction_log_migration import SourceRow


def test_index_row_keeps_folder_names_as_written() -> None:
    item = validate_index_row(
        SourceRow(
            2,
            (
                "Unit 1 Notes",
                "https://drive.example/file",
                "Class 12",
                "AI",
                "Notes",
                "Computer Vision",
                "drive-file-1",
            ),
        )
    )

    assert item.drive_file_id == "drive-file-1"
    assert item.level == "Class 12"
    assert item.subject == "AI"
    assert item.resource_type == "Notes"
    assert item.topic == "Computer Vision"


def test_missing_file_id_is_rejected() -> None:
    try:
        validate_index_row(
            SourceRow(3, ("Notes", "https://drive.example", "Class 10", "AI", "Notes", "", ""))
        )
    except ValueError as exc:
        assert "File ID" in str(exc)
    else:
        raise AssertionError("a blank File ID should be rejected")


def test_headers_must_match_the_index_sheet() -> None:
    validate_index_headers(("Title", "Link", "Level", "Subject", "Type", "Topic", "File ID"))
    try:
        validate_index_headers(("user_id", "username"))
    except ValueError as exc:
        assert "headers" in str(exc)
    else:
        raise AssertionError("wrong headers should be rejected")
