"""Create the students profile table.

Revision ID: 20261003_0002
Revises: 20260922_0001
Create Date: 2026-10-03

One row per Telegram user, matching the UserProfiles sheet columns:
user_id, username, current_class, preferred_subject, created_at,
last_updated, class_updated_year.

A blank class or subject in the sheet becomes NULL here. NULL means the
student has not chosen yet. The checks allow only classes 10-12 and subjects
AI, CS, IT, and IP.
"""

from typing import Optional, Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261003_0002"
down_revision: Optional[str] = "20260922_0001"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "username",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column("current_class", sa.SmallInteger(), nullable=True),
        sa.Column("preferred_subject", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("class_updated_year", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "current_class IS NULL OR current_class IN (10, 11, 12)",
            name="ck_students_current_class",
        ),
        sa.CheckConstraint(
            "preferred_subject IS NULL OR preferred_subject IN ('AI', 'CS', 'IT', 'IP')",
            name="ck_students_preferred_subject",
        ),
        sa.PrimaryKeyConstraint(
            "telegram_user_id",
            name="pk_students",
        ),
    )


def downgrade() -> None:
    op.drop_table("students")
