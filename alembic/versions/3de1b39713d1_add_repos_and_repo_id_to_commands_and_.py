"""add repos and repo_id to commands and env_vars

Revision ID: 3de1b39713d1
Revises: a1b32458f0f6
Create Date: 2026-04-01 23:14:22.306253

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3de1b39713d1'
down_revision: Union[str, None] = 'a1b32458f0f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'repos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('local_path', sa.Text(), nullable=True),
        sa.Column('github_url', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'slug', name='uq_project_repo_slug'),
    )

    # SQLite batch mode para agregar columnas con FK (copy-and-move)
    with op.batch_alter_table('commands') as batch_op:
        batch_op.add_column(sa.Column('repo_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_commands_repo_id', 'repos', ['repo_id'], ['id'], ondelete='SET NULL'
        )

    with op.batch_alter_table('env_variables') as batch_op:
        batch_op.add_column(sa.Column('repo_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_env_variables_repo_id', 'repos', ['repo_id'], ['id'], ondelete='SET NULL'
        )


def downgrade() -> None:
    with op.batch_alter_table('env_variables') as batch_op:
        batch_op.drop_constraint('fk_env_variables_repo_id', type_='foreignkey')
        batch_op.drop_column('repo_id')

    with op.batch_alter_table('commands') as batch_op:
        batch_op.drop_constraint('fk_commands_repo_id', type_='foreignkey')
        batch_op.drop_column('repo_id')

    op.drop_table('repos')
