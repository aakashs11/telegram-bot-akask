"""Create immutable interaction event log.

Revision ID: 20260922_0001
Revises:
Create Date: 2026-09-22
"""

from typing import Optional, Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260922_0001"
down_revision: Optional[str] = None
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "interaction_events",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("telegram_update_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("bot_response", sa.Text(), nullable=False),
        sa.Column("screener_output", sa.Text(), nullable=False),
        sa.Column("intent_output", sa.Text(), nullable=False),
        sa.Column("entities_output", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("source_timestamp_raw", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_interaction_events"),
        sa.UniqueConstraint(
            "telegram_update_id",
            name="uq_interaction_events_telegram_update_id",
        ),
        sa.UniqueConstraint(
            "source_ref",
            name="uq_interaction_events_source_ref",
        ),
    )
    op.create_index(
        "ix_interaction_events_occurred_at",
        "interaction_events",
        ["occurred_at"],
    )
    op.create_index(
        "ix_interaction_events_telegram_user_id",
        "interaction_events",
        ["telegram_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_interaction_events_telegram_user_id",
        table_name="interaction_events",
    )
    op.drop_index(
        "ix_interaction_events_occurred_at",
        table_name="interaction_events",
    )
    op.drop_table("interaction_events")
