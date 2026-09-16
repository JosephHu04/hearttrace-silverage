"""Support ordinary care records without a risk event."""
from alembic import op
import sqlalchemy as sa

revision = "20260916_0012"
down_revision = "20260916_0011"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("family_action_records") as batch:
        batch.add_column(sa.Column("elder_id", sa.String(64), nullable=True))
    op.execute("UPDATE family_action_records SET elder_id = (SELECT elder_id FROM risk_events WHERE risk_events.id = family_action_records.risk_event_id)")
    with op.batch_alter_table("family_action_records") as batch:
        batch.alter_column("elder_id", existing_type=sa.String(64), nullable=False)
        batch.create_foreign_key("fk_family_action_elder", "users", ["elder_id"], ["id"])
        batch.alter_column("risk_event_id", existing_type=sa.String(64), nullable=True)
        batch.create_index("ix_family_action_owner_elder_time", ["family_id", "elder_id", "created_at"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM family_action_records WHERE risk_event_id IS NULL")).scalar():
        raise RuntimeError("存在日常关怀记录，降级会丢失关联；请使用迁移前备份。")
    with op.batch_alter_table("family_action_records") as batch:
        batch.drop_index("ix_family_action_owner_elder_time")
        batch.drop_constraint("fk_family_action_elder", type_="foreignkey")
        batch.drop_column("elder_id")
        batch.alter_column("risk_event_id", existing_type=sa.String(64), nullable=False)
