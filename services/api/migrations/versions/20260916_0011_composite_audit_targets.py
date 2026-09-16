"""Allow audit targets containing both family and elder identifiers."""
from alembic import op
import sqlalchemy as sa

revision = "20260916_0011"
down_revision = "20260916_0010"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("audit_logs") as batch:
        batch.alter_column("target_id", existing_type=sa.String(64), type_=sa.String(160), existing_nullable=False)


def downgrade():
    count = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM audit_logs WHERE length(target_id) > 64")).scalar()
    if count:
        raise RuntimeError("审计记录包含组合编号，不能截断；请使用升级前备份回退。")
    with op.batch_alter_table("audit_logs") as batch:
        batch.alter_column("target_id", existing_type=sa.String(160), type_=sa.String(64), existing_nullable=False)
