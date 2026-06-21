"""extension_token.expires_at

Añade expires_at a extension_tokens (NOT NULL). Los tokens existentes reciben
now + 90 días como default para no romperlos agresivamente — la extensión
vieja sigue funcionando hasta esa fecha y luego pide re-login.

Revision ID: b7c4e9f1a2d3
Revises: 0a475c9a6fbc
Create Date: 2026-06-20 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import timedelta


# revision identifiers, used by Alembic.
revision: str = 'b7c4e9f1a2d3'
down_revision: Union[str, None] = '0a475c9a6fbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Añadimos la columna como nullable para poder rellenar filas existentes
    op.add_column(
        'extension_tokens',
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    )
    # 2. Backfill: tokens existentes viven 90 días desde ahora.
    op.execute(
        "UPDATE extension_tokens SET expires_at = NOW() + INTERVAL '90 days' "
        "WHERE expires_at IS NULL"
    )
    # 3. Ahora la columna es NOT NULL.
    op.alter_column('extension_tokens', 'expires_at', nullable=False)


def downgrade() -> None:
    op.drop_column('extension_tokens', 'expires_at')
