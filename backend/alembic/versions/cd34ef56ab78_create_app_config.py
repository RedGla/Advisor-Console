"""Persist administrator-configurable usage limits."""
from alembic import op
import sqlalchemy as sa
import os
from datetime import datetime, timezone

revision = "cd34ef56ab78"
down_revision = "bc23de45fa67"
branch_labels = None
depends_on = None

def upgrade() -> None:
    table = op.create_table(
        "app_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("daily_message_cap", sa.Integer(), nullable=False),
        sa.Column("daily_token_cap", sa.Integer(), nullable=False),
        sa.Column("rate_limit_requests", sa.Integer(), nullable=False),
        sa.Column("rate_limit_window_seconds", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    bind = op.get_bind()
    bind.execute(table.insert().values(
        id=1,
        daily_message_cap=int(os.getenv("MAX_MESSAGES_PER_DAY", "50")),
        daily_token_cap=int(os.getenv("MAX_TOKENS_PER_DAY", "50000")),
        rate_limit_requests=int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "5")),
        rate_limit_window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
        updated_at=datetime.now(timezone.utc),
    ))

def downgrade() -> None:
    op.drop_table("app_config")
