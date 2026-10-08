"""Add authorized, audio-only family call sessions."""

from alembic import op
import sqlalchemy as sa


revision = "20261006_0015"
down_revision = "20261003_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "voice_call_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("elder_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("family_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("caller_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_voice_calls_elder_time", "voice_call_sessions", ["elder_id", "created_at"])
    op.create_index("ix_voice_calls_family_time", "voice_call_sessions", ["family_id", "created_at"])
    op.create_index("uq_voice_calls_elder_busy", "voice_call_sessions", ["elder_id"], unique=True,
                    sqlite_where=sa.text("status IN ('ringing', 'active')"),
                    postgresql_where=sa.text("status IN ('ringing', 'active')"))
    op.create_index("uq_voice_calls_family_busy", "voice_call_sessions", ["family_id"], unique=True,
                    sqlite_where=sa.text("status IN ('ringing', 'active')"),
                    postgresql_where=sa.text("status IN ('ringing', 'active')"))


def downgrade():
    op.drop_index("uq_voice_calls_family_busy", table_name="voice_call_sessions")
    op.drop_index("uq_voice_calls_elder_busy", table_name="voice_call_sessions")
    op.drop_index("ix_voice_calls_family_time", table_name="voice_call_sessions")
    op.drop_index("ix_voice_calls_elder_time", table_name="voice_call_sessions")
    op.drop_table("voice_call_sessions")
