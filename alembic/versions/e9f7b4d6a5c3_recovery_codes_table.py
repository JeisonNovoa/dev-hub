"""recovery_codes table

Crea recovery_codes para almacenar códigos de recuperación de 2FA (10 por
usuario, hasheados con bcrypt, de un solo uso).

Revision ID: e9f7b4d6a5c3
Revises: d8e6a3c5f4b2
Create Date: 2026-06-21 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e9f7b4d6a5c3'
down_revision: Union[str, None] = 'd8e6a3c5f4b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'recovery_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('code_hash', sa.String(length=255), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_recovery_codes_user_id'),
        'recovery_codes',
        ['user_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_recovery_codes_code_hash'),
        'recovery_codes',
        ['code_hash'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_recovery_codes_code_hash'), table_name='recovery_codes')
    op.drop_index(op.f('ix_recovery_codes_user_id'), table_name='recovery_codes')
    op.drop_table('recovery_codes')
