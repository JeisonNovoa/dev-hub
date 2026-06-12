"""user totp 2fa

Revision ID: 1d2a847a6ead
Revises: 5afa8d46496b
Create Date: 2026-06-12 10:18:07.336129

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d2a847a6ead'
down_revision: Union[str, None] = '5afa8d46496b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('totp_secret', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('totp_confirmed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'totp_confirmed_at')
    op.drop_column('users', 'totp_secret')
