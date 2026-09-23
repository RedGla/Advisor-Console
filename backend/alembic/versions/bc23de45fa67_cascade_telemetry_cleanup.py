"""Allow telemetry to follow test and account cleanup."""
from alembic import op

revision = "bc23de45fa67"
down_revision = "ab12cd34ef56"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.drop_constraint("telemetry_events_user_id_fkey", "telemetry_events", type_="foreignkey")
    op.drop_constraint("telemetry_events_conversation_id_fkey", "telemetry_events", type_="foreignkey")
    op.create_foreign_key("telemetry_events_user_id_fkey", "telemetry_events", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("telemetry_events_conversation_id_fkey", "telemetry_events", "conversations", ["conversation_id"], ["id"], ondelete="CASCADE")

def downgrade() -> None:
    op.drop_constraint("telemetry_events_user_id_fkey", "telemetry_events", type_="foreignkey")
    op.drop_constraint("telemetry_events_conversation_id_fkey", "telemetry_events", type_="foreignkey")
    op.create_foreign_key("telemetry_events_user_id_fkey", "telemetry_events", "users", ["user_id"], ["id"])
    op.create_foreign_key("telemetry_events_conversation_id_fkey", "telemetry_events", "conversations", ["conversation_id"], ["id"])
