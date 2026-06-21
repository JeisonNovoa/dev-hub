"""user.password_changed_at

Añade password_changed_at a users (NOT NULL, default ahora). Sirve para
invalidar cookies de sesión server-side: si una cookie tiene iat anterior
al password_changed_at, se rechaza.

Revision ID: c9d5f2b4e3a1
Revises: b7c4e9f1a2d3
Create Date: 2026-06-20 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d5f2b4e3a1'
down_revision: Union[str, None] = 'b7c4e9f1a2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Añadir columna nullable para poder rellenar filas existentes.
    op.add_column(
        'users',
        sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True),
    )
    # 2. Backfill: ahora. Acepta cookies legacy (iat=0) hasta el siguiente cambio.
    op.execute("UPDATE users SET password_changed_at = NOW() WHERE password_changed_at IS NULL")
    # 3. NOT NULL.
    op.alter_column('users', 'password_changed_at', nullable=False)


def downgrade() -> None:
    op.drop_column('users', 'password_changed_at')
