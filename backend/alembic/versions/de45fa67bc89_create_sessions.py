"""Create server-side sessions."""
from alembic import op
import sqlalchemy as sa

revision = "de45fa67bc89"
down_revision = "cd34ef56ab78"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("sessions",
        sa.Column("token_hash", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

def downgrade() -> None:
    op.drop_table("sessions")
