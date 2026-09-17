"""Allow unmeasured summaries without inventing numeric scores."""
from alembic import op
import sqlalchemy as sa

revision = "20260916_0010"
down_revision = "20260915_0009"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("daily_insights") as batch:
        batch.alter_column("score", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("baseline_delta", existing_type=sa.Integer(), nullable=True)
    # Old values came from synthetic seeds or fixed risk-level mappings, not measurements.
    op.execute("UPDATE daily_insights SET score = NULL, baseline_delta = NULL")


def downgrade():
    raise RuntimeError("无法把未测量数据安全转换为非空分数；请恢复迁移前备份。")
