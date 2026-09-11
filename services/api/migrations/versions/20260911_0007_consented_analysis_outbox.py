"""Add consent-aware analysis outbox and structured results.

Revision ID: 20260911_0007
Revises: 20260911_0006
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260911_0007"
down_revision: Union[str, None] = "20260911_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_type", sa.String(length=40), nullable=False),
        sa.Column("aggregate_id", sa.String(length=64), nullable=False),
        sa.Column("dedupe_key", sa.String(length=160), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"])
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index(
        "ix_outbox_events_delivery",
        "outbox_events",
        ["event_type", "status", "available_at"],
    )
    op.create_index("uq_outbox_events_dedupe_key", "outbox_events", ["dedupe_key"], unique=True)

    op.create_table(
        "conversation_analyses",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("source_message_id", sa.String(length=64), nullable=False),
        sa.Column("elder_id", sa.String(length=64), nullable=False),
        sa.Column("candidate_signals", sa.JSON(), nullable=False),
        sa.Column("urgent_safety_check", sa.Boolean(), nullable=False),
        sa.Column("recommended_next_step", sa.String(length=40), nullable=False),
        sa.Column("family_summary", sa.String(length=300), nullable=False),
        sa.Column("evidence_message_ids", sa.JSON(), nullable=False),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["elder_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["conversation_sessions.id"]),
        sa.ForeignKeyConstraint(["source_message_id"], ["conversation_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversation_analyses_session_id", "conversation_analyses", ["session_id"])
    op.create_index("ix_conversation_analyses_elder_id", "conversation_analyses", ["elder_id"])
    op.create_index(
        "ix_conversation_analyses_elder_time",
        "conversation_analyses",
        ["elder_id", "created_at"],
    )
    op.create_index(
        "uq_conversation_analyses_source_message",
        "conversation_analyses",
        ["source_message_id"],
        unique=True,
    )

    with op.batch_alter_table("daily_insights") as batch_op:
        batch_op.add_column(sa.Column("source_analysis_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_daily_insights_source_analysis_id",
            "conversation_analyses",
            ["source_analysis_id"],
            ["id"],
        )
        batch_op.create_index(
            "uq_daily_insights_source_analysis",
            ["source_analysis_id"],
            unique=True,
        )

    with op.batch_alter_table("risk_events") as batch_op:
        batch_op.add_column(sa.Column("source_analysis_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_risk_events_source_analysis_id",
            "conversation_analyses",
            ["source_analysis_id"],
            ["id"],
        )
        batch_op.create_index(
            "uq_risk_events_source_analysis",
            ["source_analysis_id"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("risk_events") as batch_op:
        batch_op.drop_index("uq_risk_events_source_analysis")
        batch_op.drop_constraint("fk_risk_events_source_analysis_id", type_="foreignkey")
        batch_op.drop_column("source_analysis_id")

    with op.batch_alter_table("daily_insights") as batch_op:
        batch_op.drop_index("uq_daily_insights_source_analysis")
        batch_op.drop_constraint("fk_daily_insights_source_analysis_id", type_="foreignkey")
        batch_op.drop_column("source_analysis_id")

    op.drop_index("uq_conversation_analyses_source_message", table_name="conversation_analyses")
    op.drop_index("ix_conversation_analyses_elder_time", table_name="conversation_analyses")
    op.drop_index("ix_conversation_analyses_elder_id", table_name="conversation_analyses")
    op.drop_index("ix_conversation_analyses_session_id", table_name="conversation_analyses")
    op.drop_table("conversation_analyses")

    op.drop_index("uq_outbox_events_dedupe_key", table_name="outbox_events")
    op.drop_index("ix_outbox_events_delivery", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status", table_name="outbox_events")
    op.drop_index("ix_outbox_events_event_type", table_name="outbox_events")
    op.drop_table("outbox_events")
