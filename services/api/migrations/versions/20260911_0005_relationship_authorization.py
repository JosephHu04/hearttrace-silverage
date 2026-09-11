"""Add verified family relationship authorization.

Revision ID: 20260911_0005
Revises: 20260911_0004
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260911_0005"
down_revision: Union[str, None] = "20260911_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("registration_applications") as batch_op:
        batch_op.add_column(sa.Column("elder_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key("fk_registration_applications_elder_id", "users", ["elder_id"], ["id"])

    with op.batch_alter_table("family_elder_grants") as batch_op:
        batch_op.add_column(sa.Column("relationship", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("consent_version", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("created_by", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("updated_by", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("revoked_by", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key("fk_family_elder_grants_created_by", "users", ["created_by"], ["id"])
        batch_op.create_foreign_key("fk_family_elder_grants_updated_by", "users", ["updated_by"], ["id"])
        batch_op.create_foreign_key("fk_family_elder_grants_revoked_by", "users", ["revoked_by"], ["id"])

    op.execute("UPDATE family_elder_grants SET updated_at = created_at WHERE updated_at IS NULL")
    with op.batch_alter_table("family_elder_grants") as batch_op:
        batch_op.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch_op.alter_column("version", existing_type=sa.Integer(), server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("family_elder_grants") as batch_op:
        batch_op.drop_constraint("fk_family_elder_grants_revoked_by", type_="foreignkey")
        batch_op.drop_constraint("fk_family_elder_grants_updated_by", type_="foreignkey")
        batch_op.drop_constraint("fk_family_elder_grants_created_by", type_="foreignkey")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("version")
        batch_op.drop_column("revoked_at")
        batch_op.drop_column("revoked_by")
        batch_op.drop_column("updated_by")
        batch_op.drop_column("created_by")
        batch_op.drop_column("consent_version")
        batch_op.drop_column("relationship")

    with op.batch_alter_table("registration_applications") as batch_op:
        batch_op.drop_constraint("fk_registration_applications_elder_id", type_="foreignkey")
        batch_op.drop_column("elder_id")
