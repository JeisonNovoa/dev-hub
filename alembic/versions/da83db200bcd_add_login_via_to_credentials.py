"""add_login_via_to_credentials

Revision ID: da83db200bcd
Revises: f60310811e41
Create Date: 2026-04-02 13:42:04.187153

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da83db200bcd'
down_revision: Union[str, None] = 'f60310811e41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('credentials') as batch_op:
        batch_op.add_column(sa.Column('login_via', sa.String(20), nullable=False, server_default='email'))


def downgrade() -> None:
    with op.batch_alter_table('credentials') as batch_op:
        batch_op.drop_column('login_via')
