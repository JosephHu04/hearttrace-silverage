"""Merge notification and family care-plan migration heads.

Revision ID: 20260915_0009
Revises: 20260911_0008, 20260914_0008
Create Date: 2026-09-15
"""
from typing import Sequence, Union


revision: str = "20260915_0009"
down_revision: Union[str, Sequence[str], None] = (
    "20260911_0008",
    "20260914_0008",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
