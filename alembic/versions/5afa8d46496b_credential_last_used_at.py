"""credential last used at

Revision ID: 5afa8d46496b
Revises: 144b92a2d339
Create Date: 2026-06-12 00:49:46.912407

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5afa8d46496b'
down_revision: Union[str, None] = '144b92a2d339'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'credentials',
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('credentials', 'last_used_at')
