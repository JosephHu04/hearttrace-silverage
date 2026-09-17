"""Add consent-controlled daily elder self-reports."""

from alembic import op
import sqlalchemy as sa


revision = "20260917_0013"
down_revision = "20260916_0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "daily_check_ins",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("elder_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("checkin_date", sa.Date(), nullable=False),
        sa.Column("mood", sa.Integer(), nullable=False),
        sa.Column("sleep", sa.Integer(), nullable=False),
        sa.Column("social_willingness", sa.Integer(), nullable=False),
        sa.Column("share_with_family", sa.Boolean(), nullable=False),
        sa.Column("share_with_care_team", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("elder_id", "checkin_date", name="uq_daily_check_ins_elder_date"),
        sa.CheckConstraint("mood BETWEEN 1 AND 5", name="ck_daily_check_ins_mood"),
        sa.CheckConstraint("sleep BETWEEN 1 AND 5", name="ck_daily_check_ins_sleep"),
        sa.CheckConstraint("social_willingness BETWEEN 1 AND 5", name="ck_daily_check_ins_social"),
    )
    op.create_index("ix_daily_check_ins_elder_id", "daily_check_ins", ["elder_id"])
    op.create_index("ix_daily_check_ins_date", "daily_check_ins", ["checkin_date"])


def downgrade():
    op.drop_index("ix_daily_check_ins_date", table_name="daily_check_ins")
    op.drop_index("ix_daily_check_ins_elder_id", table_name="daily_check_ins")
    op.drop_table("daily_check_ins")
