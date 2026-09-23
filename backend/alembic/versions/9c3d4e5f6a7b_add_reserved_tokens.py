"""Track in-flight token reservations for hard daily caps."""
from alembic import op
import sqlalchemy as sa

revision = "9c3d4e5f6a7b"
down_revision = "8b2c3d4e5f6a"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("usage_counters", sa.Column("reserved_tokens_today", sa.Integer(), nullable=False, server_default="0"))

def downgrade() -> None:
    op.drop_column("usage_counters", "reserved_tokens_today")
