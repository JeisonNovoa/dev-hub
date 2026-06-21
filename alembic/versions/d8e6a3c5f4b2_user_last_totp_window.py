"""user.last_totp_window

Añade last_totp_window (BigInteger, nullable) a users. Sirve para anti-replay
de TOTP: si un código válido se reusa en la misma ventana temporal, se rechaza.

Revision ID: d8e6a3c5f4b2
Revises: c9d5f2b4e3a1
Create Date: 2026-06-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8e6a3c5f4b2'
down_revision: Union[str, None] = 'c9d5f2b4e3a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('last_totp_window', sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'last_totp_window')
