"""Pure mapping rules for the Postgres notes catalog."""

from telegram_bot.infrastructure.postgres_note_repository import (
    choose_folder_url,
    note_from_catalog,
)
from telegram_bot.services.user_service import apply_class_promotion
from datetime import datetime


def test_note_tags_follow_the_sheet_order() -> None:
    note = note_from_catalog(
        "Unit 1",
        "https://drive.example/file",
        "Class 10",
        "AI",
        "Notes",
        "Computer Vision",
    )

    assert note.tags == ["Class 10", "AI", "Notes", "Computer Vision"]
    assert note.id == "Unit 1"


def test_shortest_matching_folder_path_wins() -> None:
    rows = [
        ("Class 10/AI/Notes/Computer Vision", "https://drive.example/topic"),
        ("Class 10/AI/Notes", "https://drive.example/notes"),
    ]

    assert choose_folder_url(rows, "Class 10/AI/Notes", None) == "https://drive.example/notes"
    assert (
        choose_folder_url(rows, "Class 10/AI/Notes/Computer Vision", "Computer Vision")
        == "https://drive.example/topic"
    )


def test_sample_paper_folder_names_match_the_tool() -> None:
    rows = [
        ("Class 12/AI/Sample Question Papers SQP", "https://drive.example/12"),
        ("Class 11/CS/Sample Question papers SQP", "https://drive.example/11"),
        ("Class 12/AI/Sample Question Papers SQP/2026", "https://drive.example/12-topic"),
    ]

    assert choose_folder_url(rows, "Class 12/AI/Sample Question Papers", None) == "https://drive.example/12"
    assert choose_folder_url(rows, "Class 11/CS/Sample Question Papers", None) == "https://drive.example/11"
    assert (
        choose_folder_url(rows, "Class 12/AI/Sample Question Papers/2026", "2026")
        == "https://drive.example/12-topic"
    )


def test_sample_paper_files_use_the_tool_name() -> None:
    note = note_from_catalog(
        "Paper 1",
        "https://drive.example/paper",
        "Class 11",
        "CS",
        "Sample Question papers SQP",
        "",
    )

    assert note.tags[2] == "Sample Question Papers"


def test_class_promotion_happens_once_after_june() -> None:
    profile = {"user_id": 1, "current_class": 10, "class_updated_year": 2025}

    promoted = apply_class_promotion(profile, datetime(2026, 6, 1))
    unchanged = apply_class_promotion(promoted, datetime(2026, 6, 2))

    assert promoted["current_class"] == 11
    assert promoted["class_updated_year"] == 2026
    assert unchanged["current_class"] == 11
