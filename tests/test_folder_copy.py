"""Validation rules for the Folders sheet copy."""

from scripts.copy_folders import validate_folder_headers, validate_folder_row
from scripts.interaction_log_migration import SourceRow


def test_folder_row_keeps_the_path_the_bot_looks_up() -> None:
    folder = validate_folder_row(
        SourceRow(
            2,
            (
                "Class 10/AI/Notes",
                "folder-1",
                "https://drive.google.com/drive/folders/folder-1",
            ),
        )
    )

    assert folder.drive_folder_id == "folder-1"
    assert folder.path == "Class 10/AI/Notes"


def test_blank_path_is_rejected() -> None:
    try:
        validate_folder_row(SourceRow(3, ("", "folder-2", "https://drive.example")))
    except ValueError as exc:
        assert "Path" in str(exc)
    else:
        raise AssertionError("a blank path should be rejected")


def test_headers_must_match_the_folders_sheet() -> None:
    validate_folder_headers(("Path", "Folder ID", "URL"))
    try:
        validate_folder_headers(("Title", "Link"))
    except ValueError as exc:
        assert "headers" in str(exc)
    else:
        raise AssertionError("wrong headers should be rejected")
