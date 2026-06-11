"""extension tokens

Revision ID: 144b92a2d339
Revises: e1f2a3b4c5d6
Create Date: 2026-06-11 00:31:55.380179

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '144b92a2d339'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'extension_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_extension_tokens_token_hash'), 'extension_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_extension_tokens_user_id'), 'extension_tokens', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_extension_tokens_user_id'), table_name='extension_tokens')
    op.drop_index(op.f('ix_extension_tokens_token_hash'), table_name='extension_tokens')
    op.drop_table('extension_tokens')
