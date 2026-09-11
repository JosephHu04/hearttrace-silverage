"""Add consent-aware elder conversation sessions.

Revision ID: 20260911_0006
Revises: 20260911_0005
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260911_0006"
down_revision: Union[str, None] = "20260911_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("elder_id", sa.String(length=64), nullable=False),
        sa.Column("save_messages", sa.Boolean(), nullable=False),
        sa.Column("allow_analysis", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["elder_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversation_sessions_elder_id", "conversation_sessions", ["elder_id"])
    op.create_index(
        "ix_conversation_sessions_elder_time",
        "conversation_sessions",
        ["elder_id", "created_at"],
    )
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("processing", sa.String(length=40), nullable=True),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["conversation_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversation_messages_session_id", "conversation_messages", ["session_id"])
    op.create_index(
        "ix_conversation_messages_session_time",
        "conversation_messages",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_messages_session_time", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_session_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index("ix_conversation_sessions_elder_time", table_name="conversation_sessions")
    op.drop_index("ix_conversation_sessions_elder_id", table_name="conversation_sessions")
    op.drop_table("conversation_sessions")
