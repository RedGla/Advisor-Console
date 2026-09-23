"""Create durable telemetry events."""
from alembic import op
import sqlalchemy as sa

revision = "ab12cd34ef56"
down_revision = "9c3d4e5f6a7b"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "telemetry_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("conversation_id", sa.String(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("event", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("user_input", sa.String(), nullable=True),
        sa.Column("assistant_response", sa.String(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_telemetry_events_event", "telemetry_events", ["event"])
    op.create_index("ix_telemetry_events_user_id", "telemetry_events", ["user_id"])
    op.create_index("ix_telemetry_events_conversation_id", "telemetry_events", ["conversation_id"])

def downgrade() -> None:
    op.drop_table("telemetry_events")
