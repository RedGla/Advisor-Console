"""add conversations updated_at

Revision ID: 7a1e2f3c4d5e
Revises: 4c3448fe4bfe
Create Date: 2026-09-23 01:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a1e2f3c4d5e'
down_revision: Union[str, Sequence[str], None] = '4c3448fe4bfe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'conversations',
        sa.Column(
            'updated_at',
            sa.DateTime(),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column('conversations', 'updated_at')
