"""add deleted_at to projects (soft delete / papelera)

Revision ID: d5e3f1a2b8c4
Revises: c4e2f8a1b9d3
Create Date: 2026-04-06 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5e3f1a2b8c4"
down_revision: Union[str, None] = "c4e2f8a1b9d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("deleted_at")
