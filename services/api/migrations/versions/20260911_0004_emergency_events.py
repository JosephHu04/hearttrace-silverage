"""Add emergency event workflow.

Revision ID: 20260911_0004
Revises: 20260911_0003
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260911_0004"
down_revision: Union[str, None] = "20260911_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_elder_bindings",
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("elder_id", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["elder_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("device_id", "elder_id"),
    )
    op.create_table(
        "emergency_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("elder_id", sa.String(length=64), nullable=False),
        sa.Column("trigger_actor_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=64), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=64), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["elder_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["trigger_actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_emergency_events_request_id"),
    )
    op.create_index("ix_emergency_events_queue", "emergency_events", ["status", "created_at"], unique=False)
    op.create_index("ix_emergency_events_elder_time", "emergency_events", ["elder_id", "created_at"], unique=False)
    op.create_table(
        "emergency_actions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("emergency_event_id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=True),
        sa.Column("from_status", sa.String(length=24), nullable=False),
        sa.Column("to_status", sa.String(length=24), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["emergency_event_id"], ["emergency_events.id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_emergency_actions_request_id"),
    )
    op.create_index("ix_emergency_actions_event_time", "emergency_actions", ["emergency_event_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_emergency_actions_event_time", table_name="emergency_actions")
    op.drop_table("emergency_actions")
    op.drop_index("ix_emergency_events_elder_time", table_name="emergency_events")
    op.drop_index("ix_emergency_events_queue", table_name="emergency_events")
    op.drop_table("emergency_events")
    op.drop_table("device_elder_bindings")
