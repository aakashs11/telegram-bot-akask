"""Stop auto-assigning telegram_user_id.

Revision ID: 20261013_0003
Revises: 20261003_0002
Create Date: 2026-10-13

A lone integer primary key is created as a sequence unless autoincrement is
turned off. Telegram assigns this id. The column must not invent 1, 2, 3.
"""

from typing import Optional, Sequence, Union

from alembic import op


revision: str = "20261013_0003"
down_revision: Optional[str] = "20261003_0002"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE students ALTER COLUMN telegram_user_id DROP DEFAULT"
    )
    op.execute("DROP SEQUENCE IF EXISTS students_telegram_user_id_seq")


def downgrade() -> None:
    op.execute(
        "CREATE SEQUENCE IF NOT EXISTS students_telegram_user_id_seq"
    )
    op.execute(
        "ALTER SEQUENCE students_telegram_user_id_seq "
        "OWNED BY students.telegram_user_id"
    )
    op.execute(
        "ALTER TABLE students ALTER COLUMN telegram_user_id "
        "SET DEFAULT nextval('students_telegram_user_id_seq')"
    )
