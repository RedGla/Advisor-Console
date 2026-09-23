"""Consolidate duplicate daily usage and enforce one row per user/day.

Revision ID: 8b2c3d4e5f6a
Revises: 7a1e2f3c4d5e
"""
from alembic import op
import sqlalchemy as sa

revision = "8b2c3d4e5f6a"
down_revision = "7a1e2f3c4d5e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep writers out until consolidation AND constraint creation commit.
    op.execute(sa.text("LOCK TABLE usage_counters IN ACCESS EXCLUSIVE MODE"))
    op.execute(sa.text("""
        WITH totals AS (
            SELECT MIN(id) AS keep_id,
                   SUM(COALESCE(messages_today, 0)) AS messages,
                   SUM(COALESCE(tokens_today, 0)) AS tokens,
                   SUM(COALESCE(est_spend_today, 0)) AS spend
            FROM usage_counters
            GROUP BY user_id, date_str
            HAVING COUNT(*) > 1
        )
        UPDATE usage_counters AS counter
        SET messages_today = totals.messages,
            tokens_today = totals.tokens,
            est_spend_today = totals.spend
        FROM totals WHERE counter.id = totals.keep_id
    """))
    op.execute(sa.text("""
        DELETE FROM usage_counters AS duplicate
        USING usage_counters AS keeper
        WHERE duplicate.user_id = keeper.user_id
          AND duplicate.date_str = keeper.date_str
          AND duplicate.id > keeper.id
    """))
    op.create_unique_constraint("uq_usage_counters_user_day", "usage_counters",
                                ["user_id", "date_str"])


def downgrade() -> None:
    # Consolidated historical rows cannot be split back into their originals.
    op.drop_constraint("uq_usage_counters_user_day", "usage_counters", type_="unique")
