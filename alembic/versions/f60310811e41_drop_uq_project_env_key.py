"""drop_uq_project_env_key

Revision ID: f60310811e41
Revises: 3de1b39713d1
Create Date: 2026-04-01 23:32:38.009557

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f60310811e41'
down_revision: Union[str, None] = '3de1b39713d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('env_variables') as batch_op:
        batch_op.drop_constraint('uq_project_env_key', type_='unique')


def downgrade() -> None:
    with op.batch_alter_table('env_variables') as batch_op:
        batch_op.create_unique_constraint('uq_project_env_key', ['project_id', 'key'])
