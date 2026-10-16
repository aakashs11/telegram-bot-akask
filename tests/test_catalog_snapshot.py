"""Drive listing to catalog rows, without calling Drive or Postgres."""

from telegram_bot.services.sync_service import catalog_from_drive_files


def test_notes_path_splits_into_level_subject_type_and_topic() -> None:
    snapshot = catalog_from_drive_files(
        [
            {
                "id": "folder-class",
                "name": "Class 12",
                "mimeType": "application/vnd.google-apps.folder",
                "path": "Class 12",
            },
            {
                "id": "file-1",
                "name": "Computer Vision.pdf",
                "mimeType": "application/pdf",
                "path": "Class 12/AI/Notes/Computer Vision",
                "webViewLink": "https://drive.example/file-1",
            },
        ]
    )

    assert snapshot.folders[0]["path"] == "Class 12"
    item = snapshot.items[0]
    assert item["drive_file_id"] == "file-1"
    assert item["level"] == "Class 12"
    assert item["subject"] == "AI"
    assert item["resource_type"] == "Notes"
    assert item["topic"] == "Computer Vision"


def test_duplicate_file_id_keeps_the_first_row() -> None:
    snapshot = catalog_from_drive_files(
        [
            {
                "id": "file-1",
                "name": "First.pdf",
                "mimeType": "application/pdf",
                "path": "Class 10/AI/Notes",
                "webViewLink": "https://drive.example/first",
            },
            {
                "id": "file-1",
                "name": "Second.pdf",
                "mimeType": "application/pdf",
                "path": "Class 10/AI/Books",
                "webViewLink": "https://drive.example/second",
            },
        ]
    )

    assert len(snapshot.items) == 1
    assert snapshot.items[0]["title"] == "First.pdf"
    assert snapshot.duplicate_file_ids == 1


def test_file_without_a_path_is_skipped() -> None:
    snapshot = catalog_from_drive_files(
        [
            {
                "id": "file-2",
                "name": "Loose.pdf",
                "mimeType": "application/pdf",
                "path": "",
                "webViewLink": "https://drive.example/loose",
            }
        ]
    )

    assert snapshot.items == []
    assert snapshot.skipped == 1
