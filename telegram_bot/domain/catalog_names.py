"""Names the notes tool uses, matched to the folder text Drive stored.

Drive names the sample-paper folders "Sample Question Papers SQP".
Class 11 uses a lowercase "papers". The tool asks for "Sample Question Papers".
"""

from __future__ import annotations

_SAMPLE_PAPER_NAMES = {
    "sample question papers",
    "sample question papers sqp",
}


def canonical_resource_type(value: str) -> str:
    """Return the tool's resource name for a Drive folder segment."""
    folded = " ".join((value or "").split()).casefold()
    if folded in _SAMPLE_PAPER_NAMES:
        return "Sample Question Papers"
    return value


def canonical_catalog_path(path: str) -> str:
    """Rewrite only the resource segment of a Class/Subject/Type path."""
    parts = path.split("/")
    if len(parts) >= 3 and parts[2]:
        parts[2] = canonical_resource_type(parts[2])
    return "/".join(parts)


def catalog_paths_match(stored: str, expected: str, topic: str | None) -> bool:
    """True when two catalog paths name the same folder.

    A request without a topic also matches a folder inside that path.
    The next character must be a slash, so one type name cannot prefix another.
    """
    stored_key = canonical_catalog_path(stored)
    expected_key = canonical_catalog_path(expected)
    if stored_key == expected_key:
        return True
    if topic:
        return False
    return stored_key.startswith(expected_key + "/")
