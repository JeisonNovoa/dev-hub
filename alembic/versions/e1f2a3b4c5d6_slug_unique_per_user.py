"""slug unique per user instead of globally

Revision ID: e1f2a3b4c5d6
Revises: d5e3f1a2b8c4
Create Date: 2026-04-19 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d5e3f1a2b8c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the global unique index on slug
    op.drop_index("ix_projects_slug", table_name="projects")
    # Recreate as non-unique index for query performance
    op.create_index("ix_projects_slug", "projects", ["slug"], unique=False)
    # Add composite unique: slug is unique per user
    op.create_index("uq_projects_user_slug", "projects", ["user_id", "slug"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_projects_user_slug", table_name="projects")
    op.drop_index("ix_projects_slug", table_name="projects")
    op.create_index("ix_projects_slug", "projects", ["slug"], unique=True)
