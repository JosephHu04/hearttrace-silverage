"""Create users, risk review and audit tables.

Revision ID: 20260910_0001
Revises:
Create Date: 2026-09-10
"""
from typing import Optional, Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260910_0001"
down_revision: Optional[str] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)

    op.create_table(
        "risk_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("elder_id", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column("assignee_id", sa.String(length=64), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["elder_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_risk_events_elder_id"), "risk_events", ["elder_id"], unique=False)
    op.create_index(op.f("ix_risk_events_level"), "risk_events", ["level"], unique=False)
    op.create_index(op.f("ix_risk_events_status"), "risk_events", ["status"], unique=False)
    op.create_index("ix_risk_events_queue", "risk_events", ["level", "status", "created_at"], unique=False)

    op.create_table(
        "risk_evidence",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("risk_event_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("evidence_ref", sa.String(length=128), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["risk_event_id"], ["risk_events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_risk_evidence_risk_event_id"), "risk_evidence", ["risk_event_id"], unique=False)

    op.create_table(
        "risk_actions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("risk_event_id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["risk_event_id"], ["risk_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_risk_actions_request_id"),
    )
    op.create_index("ix_risk_actions_event_time", "risk_actions", ["risk_event_id", "created_at"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_actor_id"), "audit_logs", ["actor_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_logs_target_time", "audit_logs", ["target_type", "target_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_target_time", table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_actor_id"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_risk_actions_event_time", table_name="risk_actions")
    op.drop_table("risk_actions")
    op.drop_index(op.f("ix_risk_evidence_risk_event_id"), table_name="risk_evidence")
    op.drop_table("risk_evidence")
    op.drop_index("ix_risk_events_queue", table_name="risk_events")
    op.drop_index(op.f("ix_risk_events_status"), table_name="risk_events")
    op.drop_index(op.f("ix_risk_events_level"), table_name="risk_events")
    op.drop_index(op.f("ix_risk_events_elder_id"), table_name="risk_events")
    op.drop_table("risk_events")
    op.drop_index(op.f("ix_users_role"), "users")
    op.drop_table("users")
