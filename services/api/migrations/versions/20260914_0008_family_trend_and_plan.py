"""Add family-owned care plan items.

Revision ID: 20260914_0008
Revises: 20260911_0007
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260914_0008"
down_revision: Union[str, None] = "20260911_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "family_care_plan_items",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("elder_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=140), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["elder_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["family_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_family_care_plan_owner", "family_care_plan_items", ["family_id", "elder_id", "created_at"])
    op.create_index("ix_family_care_plan_elder", "family_care_plan_items", ["elder_id", "completed_at"])


def downgrade() -> None:
    op.drop_index("ix_family_care_plan_elder", table_name="family_care_plan_items")
    op.drop_index("ix_family_care_plan_owner", table_name="family_care_plan_items")
    op.drop_table("family_care_plan_items")
