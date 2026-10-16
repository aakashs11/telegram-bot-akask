"""Create the Drive folder table.

Revision ID: 20261013_0005
Revises: 20261013_0004
Create Date: 2026-10-13

One row per folder, matching the Folders sheet: Path, Folder ID, URL.
The bot builds a path like Class 10/AI/Notes and looks for that text.
drive_folder_id is the primary key. path is unique because that lookup
must return one folder.
"""

from typing import Optional, Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261013_0005"
down_revision: Optional[str] = "20261013_0004"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "folders",
        sa.Column("drive_folder_id", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("drive_folder_id", name="pk_folders"),
        sa.UniqueConstraint("path", name="uq_folders_path"),
    )


def downgrade() -> None:
    op.drop_table("folders")
