"""project_events (timeline de actividad del proyecto)

Revision ID: 0a475c9a6fbc
Revises: 1d2a847a6ead
Create Date: 2026-06-13 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a475c9a6fbc'
down_revision: Union[str, None] = '1d2a847a6ead'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'project_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('entity', sa.String(length=20), nullable=False),
        sa.Column('summary', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_project_events_project_id', 'project_events', ['project_id'])
    op.create_index('ix_project_events_created_at', 'project_events', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_project_events_created_at', table_name='project_events')
    op.drop_index('ix_project_events_project_id', table_name='project_events')
    op.drop_table('project_events')
