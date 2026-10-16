"""Create the content catalog table.

Revision ID: 20261013_0004
Revises: 20261013_0003
Create Date: 2026-10-13

One row per Drive file, matching the Index sheet:
Title, Link, Level, Subject, Type, Topic, File ID.

Level, subject, and type are folder names as the sync wrote them
("Class 12", "AI", "Notes", and also "General" or "College").
Topic is the rest of the path, so "Computer Vision" belongs here.
Those columns are text with no check. The profile checks on students
do not apply to the catalog.
"""

from typing import Optional, Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261013_0004"
down_revision: Optional[str] = "20261013_0003"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "content_items",
        sa.Column("drive_file_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("link", sa.Text(), nullable=False, server_default=""),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("drive_file_id", name="pk_content_items"),
    )
    op.create_index(
        "ix_content_items_level_subject_type",
        "content_items",
        ["level", "subject", "resource_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_content_items_level_subject_type",
        table_name="content_items",
    )
    op.drop_table("content_items")
