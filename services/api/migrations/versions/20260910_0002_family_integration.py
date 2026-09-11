"""Add family authorization, daily insights and care actions.

Revision ID: 20260910_0002
Revises: 20260910_0001
Create Date: 2026-09-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260910_0002"
down_revision: Union[str, None] = "20260910_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "elder_profiles",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "family_elder_grants",
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("elder_id", sa.String(length=64), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["elder_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["family_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("family_id", "elder_id"),
    )
    op.create_table(
        "daily_insights",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("elder_id", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("headline", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("baseline_delta", sa.Integer(), nullable=False),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("has_active_emergency", sa.Boolean(), nullable=False),
        sa.Column("safety_message", sa.String(length=300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["elder_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_daily_insights_elder_id"), "daily_insights", ["elder_id"], unique=False)
    op.create_index("ix_daily_insights_elder_time", "daily_insights", ["elder_id", "created_at"], unique=False)
    op.create_table(
        "family_action_records",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("risk_event_id", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["risk_event_id"], ["risk_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_family_action_records_request_id"),
    )
    op.create_index("ix_family_action_event_time", "family_action_records", ["risk_event_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_family_action_event_time", table_name="family_action_records")
    op.drop_table("family_action_records")
    op.drop_index("ix_daily_insights_elder_time", table_name="daily_insights")
    op.drop_index(op.f("ix_daily_insights_elder_id"), table_name="daily_insights")
    op.drop_table("daily_insights")
    op.drop_table("family_elder_grants")
    op.drop_table("elder_profiles")
