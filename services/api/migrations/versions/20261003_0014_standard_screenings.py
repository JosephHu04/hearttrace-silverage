"""Add versioned, consent-controlled standard screening records."""

from alembic import op
import sqlalchemy as sa


revision = "20261003_0014"
down_revision = "20260917_0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "screening_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("elder_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("instrument_code", sa.String(32), nullable=False),
        sa.Column("instrument_version", sa.String(32), nullable=False),
        sa.Column("standard_reference", sa.String(120), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("share_with_family", sa.Boolean(), nullable=False),
        sa.Column("share_with_care_team", sa.Boolean(), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=True),
        sa.Column("result_band", sa.String(24), nullable=True),
        sa.Column("recommendation", sa.String(500), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_screening_sessions_elder_id", "screening_sessions", ["elder_id"])
    op.create_index("ix_screening_sessions_status", "screening_sessions", ["status"])
    op.create_index("ix_screening_sessions_elder_time", "screening_sessions", ["elder_id", "created_at"])
    op.create_index(
        "ix_screening_sessions_staff_queue",
        "screening_sessions",
        ["share_with_care_team", "status", "completed_at"],
    )

    op.create_table(
        "screening_answers",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(64), sa.ForeignKey("screening_sessions.id"), nullable=False),
        sa.Column("item_code", sa.String(32), nullable=False),
        sa.Column("response_value", sa.String(16), nullable=False),
        sa.Column("score_value", sa.Integer(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "item_code", name="uq_screening_answers_session_item"),
    )
    op.create_index("ix_screening_answers_session_id", "screening_answers", ["session_id"])
    op.create_index("ix_screening_answers_session_time", "screening_answers", ["session_id", "answered_at"])


def downgrade():
    op.drop_index("ix_screening_answers_session_time", table_name="screening_answers")
    op.drop_index("ix_screening_answers_session_id", table_name="screening_answers")
    op.drop_table("screening_answers")
    op.drop_index("ix_screening_sessions_staff_queue", table_name="screening_sessions")
    op.drop_index("ix_screening_sessions_elder_time", table_name="screening_sessions")
    op.drop_index("ix_screening_sessions_status", table_name="screening_sessions")
    op.drop_index("ix_screening_sessions_elder_id", table_name="screening_sessions")
    op.drop_table("screening_sessions")
