"""Add durable in-app notifications.

Revision ID: 20260911_0008
Revises: 20260911_0007
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260911_0008"
down_revision: Union[str, None] = "20260911_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_records",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("recipient_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.String(length=500), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("dedupe_key", sa.String(length=80), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_records_recipient_id", "notification_records", ["recipient_id"])
    op.create_index("ix_notification_records_category", "notification_records", ["category"])
    op.create_index(
        "ix_notification_records_recipient_time",
        "notification_records",
        ["recipient_id", "created_at"],
    )
    op.create_index(
        "ix_notification_records_recipient_unread",
        "notification_records",
        ["recipient_id", "is_read", "created_at"],
    )
    op.create_index(
        "uq_notification_records_dedupe_key",
        "notification_records",
        ["dedupe_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_notification_records_dedupe_key", table_name="notification_records")
    op.drop_index("ix_notification_records_recipient_unread", table_name="notification_records")
    op.drop_index("ix_notification_records_recipient_time", table_name="notification_records")
    op.drop_index("ix_notification_records_category", table_name="notification_records")
    op.drop_index("ix_notification_records_recipient_id", table_name="notification_records")
    op.drop_table("notification_records")
