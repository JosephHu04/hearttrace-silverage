"""Add family registration approval and password recovery.

Revision ID: 20260911_0003
Revises: 20260910_0002
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260911_0003"
down_revision: Union[str, None] = "20260910_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("login_identifier", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(length=256), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("uq_users_login_identifier", "users", ["login_identifier"], unique=True)
    op.create_table(
        "registration_applications",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("login_identifier", sa.String(length=120), nullable=False),
        sa.Column("relationship", sa.String(length=80), nullable=False),
        sa.Column("elder_name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("consent_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("review_note", sa.String(length=500), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_registration_applications_queue", "registration_applications", ["status", "created_at"], unique=False)
    op.create_index("ix_registration_applications_login_identifier", "registration_applications", ["login_identifier"], unique=True)
    op.create_index(op.f("ix_registration_applications_status"), "registration_applications", ["status"], unique=False)
    op.create_table(
        "password_recovery_tokens",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_password_recovery_tokens_lookup", "password_recovery_tokens", ["token_hash", "expires_at"], unique=False)
    op.create_index(op.f("ix_password_recovery_tokens_user_id"), "password_recovery_tokens", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_password_recovery_tokens_lookup", table_name="password_recovery_tokens")
    op.drop_index(op.f("ix_password_recovery_tokens_user_id"), table_name="password_recovery_tokens")
    op.drop_table("password_recovery_tokens")
    op.drop_index(op.f("ix_registration_applications_status"), table_name="registration_applications")
    op.drop_index("ix_registration_applications_login_identifier", table_name="registration_applications")
    op.drop_index("ix_registration_applications_queue", table_name="registration_applications")
    op.drop_table("registration_applications")
    op.drop_index("uq_users_login_identifier", table_name="users")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "login_identifier")
